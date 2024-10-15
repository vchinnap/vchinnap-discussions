import requests
import os

GITHUB_TOKEN = os.getenv("G_TOKEN")  # Set your GitHub token with the appropriate permissions
GITHUB_API_URL = "https://api.github.com/graphql"

# Replace with your actual team ID from the organization
TEAM_ID = "YOUR_TEAM_ID"  

def create_team_discussion_category(category_name, category_description):
    query = """
    mutation($teamId: ID!, $name: String!, $description: String!) {
      createTeamDiscussionCategory(input: {
        teamId: $teamId,
        name: $name,
        description: $description
      }) {
        category {
          id
          name
        }
      }
    }
    """

    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

    variables = {
        "teamId": TEAM_ID,
        "name": category_name,
        "description": category_description
    }

    response = requests.post(
        GITHUB_API_URL,
        json={'query': query, 'variables': variables},
        headers=headers
    )

    if response.status_code == 200:
        data = response.json()
        if 'errors' in data:
            print(f"Error creating category '{category_name}': {data['errors']}")
        else:
            print(f"Category '{category_name}' created successfully.")
    else:
        raise Exception(f"Failed to create category: {response.content}")


if __name__ == "__main__":
    categories = [
        {"name": "General", "description": "General discussions"},
        {"name": "Q&A", "description": "Questions and answers"},
        {"name": "Announcements", "description": "Official announcements"}
    ]

    for category in categories:
        create_team_discussion_category(category["name"], category["description"])
