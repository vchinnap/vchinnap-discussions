 # Fetch tags for the resource
                    try:
                        tags = backup_client.list_tags(ResourceArn=job.get("ResourceArn", ""))
                        support_team = next((tag["Value"] for tag in tags.get("Tags", []) if tag["Key"] == "Support-Team"), "N/A")
                    except Exception as tag_error:
                        logging.error(f"Error fetching tags for resource {resource_id}: {str(tag_error)}")
                        support_team = "N/A"
