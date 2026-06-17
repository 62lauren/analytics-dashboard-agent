import os

import pandas as pd
import requests
from simple_salesforce import Salesforce


class SalesforceClient:
    QUERYABLE_OBJECTS = [
        "Opportunity",
        "Lead",
        "Account",
        "Contact",
        "Case",
        "Task",
        "Event",
        "Campaign",
        "Product2",
        "OpportunityLineItem",
    ]

    def __init__(self):
        domain = os.environ.get("SALESFORCE_DOMAIN", "login")
        client_id = os.environ.get("SALESFORCE_CLIENT_ID")
        client_secret = os.environ.get("SALESFORCE_CLIENT_SECRET")

        if client_id and client_secret:  # required for newer Salesforce orgs
            session_id, instance_url = self._oauth_login(domain, client_id, client_secret)
            self._sf = Salesforce(session_id=session_id, instance_url=instance_url)
        else:
            self._sf = Salesforce(
                username=os.environ["SALESFORCE_USERNAME"],
                password=os.environ["SALESFORCE_PASSWORD"],
                security_token=os.environ["SALESFORCE_SECURITY_TOKEN"],
                domain=domain,
            )

    def _oauth_login(self, domain: str, client_id: str, client_secret: str) -> tuple[str, str]:
        instance = os.environ.get("SALESFORCE_INSTANCE_URL")
        base = f"https://{instance}" if instance else f"https://{domain}.salesforce.com"
        url = f"{base}/services/oauth2/token"
        resp = requests.post(url, data={
            "grant_type": "client_credentials",
            "client_id": client_id,
            "client_secret": client_secret,
        })
        if not resp.ok:
            raise Exception(f"Salesforce OAuth error {resp.status_code}: {resp.text}")
        data = resp.json()
        if "error" in data:
            raise Exception(f"Salesforce OAuth error: {data['error']} — {data.get('error_description', '')}")
        return data["access_token"], data["instance_url"]

    def list_objects(self) -> list[dict]:
        describe = self._sf.describe()
        available = {s["name"] for s in describe["sobjects"]}
        return [
            {"name": name, "label": name.replace("_", " ")}
            for name in self.QUERYABLE_OBJECTS
            if name in available
        ]

    def describe_object(self, object_name: str) -> list[dict]:
        obj = getattr(self._sf, object_name)
        fields = obj.describe()["fields"]
        return [
            {
                "name": f["name"],
                "label": f["label"],
                "type": f["type"],
                "updateable": f["updateable"],
            }
            for f in fields
            if not f.get("deprecatedAndHidden", False)
            and f["type"] not in ("address", "location")
        ]

    def query(self, soql: str) -> list[dict]:
        result = self._sf.query_all(soql)
        records = result.get("records", [])
        flat = [self._flatten(r) for r in records]
        if not flat:
            return []
        df = pd.DataFrame(flat)
        for col in df.columns:
            try:
                df[col] = pd.to_numeric(df[col])
            except (ValueError, TypeError):
                pass
        return df.to_dict(orient="records")

    def _flatten(self, record: dict, prefix: str = "") -> dict:
        out: dict = {}
        for key, value in record.items():
            if key == "attributes":
                continue
            full_key = f"{prefix}.{key}" if prefix else key
            if isinstance(value, dict):
                out.update(self._flatten(value, full_key))
            else:
                out[full_key] = value
        return out
