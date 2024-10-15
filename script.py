import requests
import json
import os

GITHUB_TOKEN = os.getenv("G_TOKEN")
REPO_OWNER = "vchinnap"  # Change this to your GitHub username
REPO_NAME = "town-square"  # Change this to your repository name

# GitHub GraphQL endpoint
GITHUB_API_URL = "https://api.github.com/graphql"

# GraphQL mutation to create a discussion category
def create_discussion_category(category_name, category_description):
    query = """
    mutation($repositoryId: ID!, $name: String!, $description: String!) {
      createDiscussionCategory(input: {
        repositoryId: $repositoryId,
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

    # Get repository ID
    repo_id = get_repository_id()

    variables = {
        "repositoryId": repo_id,
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
        print(f"Category '{category_name}' created successfully.")
    else:
        raise Exception(f"Failed to create category: {response.content}")

def get_repository_id():
    query = """
    query($owner: String!, $name: String!) {
      repository(owner: $owner, name: $name) {
        id
      }
    }
    """
    
    variables = {"owner": REPO_OWNER, "name": REPO_NAME}

    headers = {"Authorization": f"Bearer {GITHUB_TOKEN}"}

    response = requests.post(
        GITHUB_API_URL,
        json={'query': query, 'variables': variables},
        headers=headers
    )

    # Add debug statements
    print("Response status code:", response.status_code)
    print("Response content:", response.content)

    if response.status_code == 200:
        data = response.json()
        if 'data' in data and 'repository' in data['data']:
            return data['data']['repository']['id']
        else:
            raise Exception(f"Repository not found in the response: {data}")
    else:
        raise Exception(f"Failed to fetch repository ID: {response.content}")


if __name__ == "__main__":
    categories = [
        {"name": "General", "description": "General discussions"},
        {"name": "Q&A", "description": "Question and answer category"},
        {"name": "Announcements", "description": "Official announcements"},
    ]

    for category in categories:
        create_discussion_category(category["name"], category["description"])
