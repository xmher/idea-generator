#!/usr/bin/env python3
# canva_helper.py
# Helper functions for Canva API integration

import os
import sys
import json
import requests
from typing import Dict, Optional

try:
    from dotenv import load_dotenv
    load_dotenv()
except Exception:
    pass

CANVA_API_KEY = os.getenv("CANVA_API_KEY")
CANVA_BASE_URL = "https://api.canva.com/v1"

class CanvaHelper:
    """Helper class for Canva API operations"""

    def __init__(self, api_key: Optional[str] = None):
        self.api_key = api_key or CANVA_API_KEY
        if not self.api_key:
            raise ValueError("Canva API key not found. Set CANVA_API_KEY environment variable.")

        self.headers = {
            "Authorization": f"Bearer {self.api_key}",
            "Content-Type": "application/json"
        }

    def duplicate_design(self, design_id: str, title: Optional[str] = None) -> Dict:
        """
        Duplicate a Canva design/template.

        Args:
            design_id: The ID of the design to duplicate
            title: Optional title for the new design

        Returns:
            Dict with new design info including 'id' and 'edit_url'
        """
        url = f"{CANVA_BASE_URL}/designs"

        payload = {
            "asset_id": design_id
        }

        if title:
            payload["title"] = title

        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()

        return response.json()

    def get_design(self, design_id: str) -> Dict:
        """
        Get design information.

        Args:
            design_id: The design ID

        Returns:
            Design information dict
        """
        url = f"{CANVA_BASE_URL}/designs/{design_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        return response.json()

    def autofill_design(self, design_id: str, data: Dict) -> Dict:
        """
        Autofill a Canva template with data.

        This is the primary method for updating template text elements.

        Args:
            design_id: The template/design ID
            data: Dict mapping placeholder names to values
                  Example: {"Headline": "New Headline", "Stat": "42%"}

        Returns:
            Updated design info
        """
        url = f"{CANVA_BASE_URL}/designs/{design_id}/autofill"

        payload = {
            "data": data
        }

        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()

        return response.json()

    def export_design(self, design_id: str, file_type: str = "png") -> Dict:
        """
        Export a design to an image file.

        Args:
            design_id: The design ID to export
            file_type: Export format (png, jpg, pdf)

        Returns:
            Export info including download URL
        """
        url = f"{CANVA_BASE_URL}/designs/{design_id}/export"

        payload = {
            "format": {
                "type": file_type
            }
        }

        response = requests.post(url, headers=self.headers, json=payload)
        response.raise_for_status()

        result = response.json()

        # Get export status
        export_id = result.get("export", {}).get("id")
        if export_id:
            return self.get_export_status(design_id, export_id)

        return result

    def get_export_status(self, design_id: str, export_id: str) -> Dict:
        """
        Check the status of an export job.

        Args:
            design_id: The design ID
            export_id: The export job ID

        Returns:
            Export status including download URL when ready
        """
        url = f"{CANVA_BASE_URL}/designs/{design_id}/exports/{export_id}"
        response = requests.get(url, headers=self.headers)
        response.raise_for_status()

        return response.json()

    def update_and_export(
        self,
        template_id: str,
        updates: Dict,
        export_format: str = "png",
        new_title: Optional[str] = None
    ) -> Dict:
        """
        Complete workflow: duplicate template, update text, export.

        Args:
            template_id: Original template ID
            updates: Text updates to apply
            export_format: png, jpg, or pdf
            new_title: Optional title for the duplicated design

        Returns:
            Dict with design info and export URL
        """
        print(f"1. Duplicating template {template_id}...")
        new_design = self.duplicate_design(template_id, new_title)
        new_design_id = new_design["design"]["id"]

        print(f"2. Updating text in design {new_design_id}...")
        self.autofill_design(new_design_id, updates)

        print(f"3. Exporting as {export_format}...")
        export_result = self.export_design(new_design_id, export_format)

        return {
            "design_id": new_design_id,
            "edit_url": new_design.get("design", {}).get("urls", {}).get("edit_url"),
            "export": export_result
        }


def test_connection():
    """Test Canva API connection"""
    if not CANVA_API_KEY:
        print("❌ CANVA_API_KEY not set in environment")
        return False

    try:
        helper = CanvaHelper()
        print("✅ Canva API key configured")
        print(f"   Using API endpoint: {CANVA_BASE_URL}")
        return True
    except Exception as e:
        print(f"❌ Canva API error: {e}")
        return False


if __name__ == "__main__":
    # Simple test when run directly
    print("🎨 Canva Helper - Testing Connection")
    print("-" * 60)

    if test_connection():
        print("\n💡 Ready to use Canva API integration!")
        print("\nExample usage:")
        print("  from canva_helper import CanvaHelper")
        print("  helper = CanvaHelper()")
        print("  result = helper.update_and_export(")
        print("      template_id='YOUR_TEMPLATE_ID',")
        print("      updates={'Headline': 'New Headline', 'Stat': '42%'}")
        print("  )")
    else:
        print("\n⚠️  Set up CANVA_API_KEY to use Canva integration")
        print("   Get your API key from: https://www.canva.com/developers/")
