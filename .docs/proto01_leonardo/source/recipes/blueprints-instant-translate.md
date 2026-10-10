---
updatedAt: 2026-01-29T00:56:52.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Blueprints: Instant Translate

```python Python
import requests
import time

api_key = "<YOUR_API_KEY>"
authorization = "Bearer %s" % api_key

headers = {
    "accept": "application/json",
    "content-type": "application/json",
    "authorization": authorization
}

# 1) Execute Blueprint
url = "https://cloud.leonardo.ai/api/rest/v1/blueprint-executions"

payload = {
    "blueprintVersionId": "7ebfcc4c-503f-4bc3-8efd-a64338e9315c",
    "input": {
        "nodeInputs": [
            {
                "value": "https://cdn.leonardo.ai/blueprint_assets/official/384ab5c8-55d8-47a1-be22-6a274913c324/thumbnails/thumbnail-a909d4.jpg",
                "nodeId": "7f9c1c8a-7d16-4bc8-bc4c-5b72d7653c12",
                "settingName": "imageUrl"
            },
            {
                "value": [{"name": "language", "value": "Spanish"}],
                "nodeId": "16c99a94-9b47-4f2d-b3ff-7e6a82d7d891",
                "settingName": "textVariables"
            }
        ],
        "public": False,
        "collectionIds": []
    }
}

response = requests.post(url, json=payload, headers=headers)
print("Execute Blueprint: %s" % response.status_code)

execution_id = response.json()["executeBlueprint"]["akUUID"]
print("Blueprint Execution ID: %s" % execution_id)

# 2) Get Blueprint Generations
time.sleep()

url = "https://cloud.leonardo.ai/api/rest/v1/blueprint-executions/%s/generations" % execution_id
response = requests.get(url, headers=headers)
print("Get Blueprint Generations: %s" % response.status_code)

generation_id = response.json()["blueprintExecutionGenerations"]["edges"][0]["node"]["generationId"]
print("Generation ID: %s" % generation_id)

# 3) Get the generated image
url = "https://cloud.leonardo.ai/api/rest/v1/generations/%s" % generation_id
response = requests.get(url, headers=headers)
print("Get Generation: %s" % response.status_code)

print(response.text)
```

# Execute Blueprint

<!-- python@1-40 -->

This command executes the Blueprint.

To use this command, replace \<YOUR_API_KEY> with your API key and run it in your terminal.

The response will contain an akUUID you will need in the next step.

# Get Blueprint Generations

<!-- python@42-50 -->

Replace \<YOUR_AKUUID> with the akUUID returned from Step 1.

This response will include a generationId once the execution is COMPLETED.

# Get the generated image

<!-- python@52-57 -->

Replace \<YOUR_GENERATION_ID> with the generationId returned from Step 2.

The response contains the output image URL at generated_images[0].url.