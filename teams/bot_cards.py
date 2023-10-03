
import json


def create_settings_card(message, strings_values):
    cards = {
        "type": "AdaptiveCard",
        "version": "1.2",
        "body": [
            {
                "type": "TextBlock",
                "size": "medium",
                "weight": "Bolder",
                "horizontalAlignment": "Left",
                "text": message
            },
            {
                "type": "Input.ChoiceSet",
                "id": "acDecision",
                "value": "1",
                "wrap": True,
                "choices": [],
                "style": "expanded"
            }
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Change",
                "id": "btnChange"
            }
        ]
    }

    for index, (title, value) in enumerate(strings_values):
        cards["body"][1]["choices"].append({
            "title": title,
            "value": value
        })

    return json.dumps(cards)


def create_setting_card(message, setting_name, setting_desc, current_value):
    
    cards = {
        "type": "AdaptiveCard",
        "version": "1.2",
        "body": [
            {
                "type": "Container",
                "items": [
                    {
                        "type": "TextBlock",
                        "size": "medium",
                        "weight": "Bolder",
                        "horizontalAlignment": "Left",
                        "text": setting_name
                    },
                    {
                        "type": "TextBlock",
                        "text": setting_desc,
                        "wrap": True
                    },
                    {
                        "type": "TextBlock",
                        "text": f"Current Value: {current_value}",
                        "wrap": True
                    }
                    
                ]
            },
            {
                "type": "Container",
                "items": [
                    {
                        "type": "Input.Text",
                        "id": "setting",
                        "placeholder": current_value,
                        "label": "New Value:"
                    }
                ]
            }
        ],
        "actions": [
            {
                "type": "Action.Submit",
                "title": "Update",
                "data": {
                    "acDecision": f"userman set setting {setting_name}"
                }
            }
            
        ]
    }

    return json.dumps(cards)