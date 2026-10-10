---
updatedAt: 2026-01-29T01:14:53.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/llms.txt
---

# Blueprints Guide

Execute Leonardo's Blueprints via the Production API to create faster and effortlessly get great results.

**Recipe:**

<Recipe slug="blueprints-instant-translate" title="Blueprints: Instant Translate" />

<br />

**In this guide:**

* Choosing a Blueprint that fits your needs
* Preparing your inputs and understanding requirements
* Running the Blueprint and monitoring progress
* Getting your generated outputs

<br />

**Blueprint Workflow:**

| Step              | Endpoint                                     | Required    |
| ----------------- | -------------------------------------------- | ----------- |
| List Blueprints   | `GET /blueprints`                            | If browsing |
| Get Details       | `GET /blueprints/{id}`                       | -           |
| Get Version       | `GET /blueprints/{id}/versions`              | ✓           |
| Execute           | `POST /blueprint-executions`                 | ✓           |
| Check Status      | `GET /blueprint-executions/{id}`             | -           |
| Get Generation ID | `GET /blueprint-executions/{id}/generations` | ✓           |
| Retrieve Outputs  | `GET /generations/{id}`                      | ✓           |

***

## What are Blueprints?

Blueprints are Leonardo's new way to create - a suite of AI workflows designed to help you achieve awesome results fast. Blueprints don't limit creativity - they expand it. Think of them as creative fuel: a launchpad for imagination that gives you the freedom to explore, experiment, and go further than before.

Blueprints make AI accessible, stable, and intuitive. No complex setup. No endless trial and error. Just find a Blueprint you like, implement, and watch your idea come to life.

***

## Choosing a Blueprint

Before you can run a Blueprint, you need to find one that matches your creative goal and understand what it does.

### List Available Blueprints

Retrieve the list of all Blueprints available via the API.

```curl
curl --request GET \
  --url https://cloud.leonardo.ai/api/rest/v1/blueprints \
  --header 'accept: application/json' \
  --header 'authorization: Bearer <YOUR_API_KEY>' \
  --header 'content-type: application/json' \
  --data '{
    "first": 10,
    "platforms": ["API"]
  }'
```

**Filtering Results**

Use the `first` parameter to limit results and `platforms: ["API"]` to only show Blueprints available via API.

### Get Blueprint Details

Get detailed information about a specific Blueprint.

*Note: This is an optional step for previewing Blueprint information.*

```curl
curl --request GET \
  --url https://cloud.leonardo.ai/api/rest/v1/blueprints/BLUEPRINT_akUUID_HERE \
  --header 'accept: application/json' \
  --header 'authorization: Bearer <YOUR_API_KEY>'
```

***

## Preparing Your Inputs

Once you've chosen a Blueprint, prepare the specific inputs it requires.

### Understanding Blueprint Structure

Blueprints use a node-based workflow where each step is a node. When providing inputs:

1. Each input has a `nodeId` identifying which step it belongs to
2. The `settingName` identifies which parameter within that node
3. The `value` provides the actual input data

Get the correct `nodeId` and `settingName` from the Blueprint Versions endpoint.

### Get Blueprint Version

This endpoint allows you to retrieve the Blueprint version to get the `blueprintVersionId` needed for execution, as well as understand the input schema.

```curl
curl --request GET \
  --url https://cloud.leonardo.ai/api/rest/v1/blueprints/BLUEPRINT_akUUID_HERE/versions \
  --header 'accept: application/json' \
  --header 'authorization: Bearer <YOUR_API_KEY>'
```

**Example Response:**

```json
{
    "blueprintVersions": {
        "edges": [
            {
                "cursor": "eyJjcmVhdGVkQXQiOiIyMDI1LTExLTI3VDA1OjEzOjIxLjg5NloiLCJha1VVSUQiOiI3ZWJmY2M0Yy01MDNmLTRiYzMtOGVmZC1hNjQzMzhlOTMxNWMifQ==",
                "node": {
                    "akUUID": "7ebfcc4c-503f-4bc3-8efd-a64338e9315c",
                    "createdAt": "2025-11-27T05:13:21.896Z",
                    "updatedAt": "2025-11-27T05:13:21.896Z",
                    "cost": 1,
                    "uiMetadata": {
                        "inputs": [
                            {
                                "type": "image",
                                "label": "Upload Image to Translate",
                                "nodeId": "7f9c1c8a-7d16-4bc8-bc4c-5b72d7653c12",
                                "required": true,
                                "settingName": "imageUrl"
                            },
                            {
                                "type": "text",
                                "label": "Target Language",
                                "nodeId": "16c99a94-9b47-4f2d-b3ff-7e6a82d7d891",
                                "required": true,
                                "variable": "language",
                                "placeholder": "e.g., Spanish, French, Japanese",
                                "settingName": "textVariables"
                            }
                        ],
                        "outputs": [
                            {
                                "type": "image"
                            }
                        ]
                    },
                    "uiMetadataSchemaVersion": "21",
                    "models": [
                        "gemini-image-2"
                    ],
                    "executability": {
                        "isExecutable": true,
                        "reasons": []
                    }
                }
            }
        ],
        "totalCount": 1,
        "pageInfo": {
            "hasNextPage": false,
            "hasPreviousPage": false,
            "startCursor": "eyJjcmVhdGVkQXQiOiIyMDI1LTExLTI3VDA1OjEzOjIxLjg5NloiLCJha1VVSUQiOiI3ZWJmY2M0Yy01MDNmLTRiYzMtOGVmZC1hNjQzMzhlOTMxNWMifQ==",
            "endCursor": "eyJjcmVhdGVkQXQiOiIyMDI1LTExLTI3VDA1OjEzOjIxLjg5NloiLCJha1VVSUQiOiI3ZWJmY2M0Yy01MDNmLTRiYzMtOGVmZC1hNjQzMzhlOTMxNWMifQ=="
        }
    }
}
```

**Understanding the Response:**

* **akUUID** (`7ebfcc4c-503f-4bc3-8efd-a64338e9315c`): The version ID to pass into the Execute Blueprint endpoint as `blueprintVersionId`
* **cost**: Cost  to execute this Blueprint
* **uiMetadata.inputs**: Shows the required inputs with their `nodeId` and `settingName` - use these exact values when executing
  * 1 image input (`imageUrl`)
  * 1 text input (`textVariables` with variable `language`)
* **uiMetadata.outputs**: Shows what the Blueprint will generate (1 image)

***

### Pattern Examples for Different Input Types

Blueprints accept various input types. Here's how to work with each:

#### Image URL Inputs

Reference Leonardo hosted images:

```json
{
  "nodeInputs": [
    {
      "value": "https://cdn.leonardo.ai/users/.../image.jpg",
      "nodeId": "nodeID-1",
      "settingName": "imageUrl"
    }
  ]
}
```

**Image URL Requirements**

Images must be hosted on Leonardo's CDN. Use [Get Init Image by ID](https://docs.leonardo.ai/reference/getinitimagebyid) to return the URL for an Init Image.

To use your own images, first upload them using the [Upload Init Image API](https://docs.leonardo.ai/docs/how-to-upload-an-image-using-a-presigned-url).

#### Text Variable Inputs

Provide text parameters with variable name:

```json
{
  "nodeInputs": [
    {
      "value": [
        {
          "name": "language",
          "value": "Spanish"
        }
      ],
      "nodeId": "nodeID-1",
      "settingName": "textVariables"
    }
  ]
}
```

#### Multiple Inputs Combined

Many Blueprints require several inputs:

```json
{
  "blueprintVersionId": "7ebfcc4c-503f-4bc3-8efd-a64338e9315c",
  "input": {
    "nodeInputs": [
      {
        "value": "https://cdn.leonardo.ai/users/.../source.jpg",
        "nodeId": "nodeID-1",
        "settingName": "sourceImage"
      },
      {
        "value": [
          {
            "name": "language",
            "value": "Spanish"
          }
        ],
        "nodeId": "nodeID-2",
        "settingName": "textVariables"
      }
    ],
    "public": false,
    "collectionIds": []
  }
}
```

***

## Running the Blueprint

With your inputs prepared, execute the Blueprint and monitor its progress.

### Execute the Blueprint

Execute the Blueprint with your inputs. Note that image URLs must be hosted on the Leonardo platform.

```curl
curl --request POST \
  --url https://cloud.leonardo.ai/api/rest/v1/blueprint-executions \
  --header 'accept: application/json' \
  --header 'authorization: Bearer <YOUR_API_KEY>' \
  --header 'content-type: application/json' \
  --data '{
  "blueprintVersionId": "7ebfcc4c-503f-4bc3-8efd-a64338e9315c",
  "input": {
    "nodeInputs": [
      {
        "value": "https://cdn.leonardo.ai/users/.../source.jpg",
        "nodeId": "7f9c1c8a-7d16-4bc8-bc4c-5b72d7653c12",
        "settingName": "imageUrl"
      },
      {
        "value": [
          {
            "name": "language",
            "value": "Spanish"
          }
        ],
        "nodeId": "16c99a94-9b47-4f2d-b3ff-7e6a82d7d891",
        "settingName": "textVariables"
      }
    ],
    "public": false,
    "collectionIds": []
  }
}'
```

**Example Response:**

```json
{
  "executeBlueprint": {
    "akUUID": "YOUR_akUUID_HERE"
  }
}
```

**Important Notes**

* Image URLs must be Leonardo hosted (either from generations or uploaded assets)
* Save the execution ID (`akUUID`) - you'll need it to poll for results

### Check Execution Status

After executing a Blueprint, you can check the status of your execution and review the inputs you submitted.

*Note: This is an optional confirmation step. You can proceed directly to getting the generation ID.*

```curl
curl --request GET \
  --url https://cloud.leonardo.ai/api/rest/v1/blueprint-executions/YOUR_akUUID_HERE \
  --header 'accept: application/json' \
  --header 'authorization: Bearer <YOUR_API_KEY>'
```

**Example Response:**

```json
{
    "blueprintExecution": {
        "akUUID": "YOUR_akUUID_HERE",
        "status": "COMPLETED",
        "inputs": [
            {
                "value": "https://cdn.leonardo.ai/users/.../source.jpg",
                "nodeId": "7f9c1c8a-7d16-4bc8-bc4c-5b72d7653c12",
                "settingName": "imageUrl"
            },
            {
                "value": [
                    {
                        "name": "language",
                        "value": "Spanish"
                    }
                ],
                "nodeId": "16c99a94-9b47-4f2d-b3ff-7e6a82d7d891",
                "settingName": "textVariables"
            }
        ],
        "public": false,
        "createdAt": "2026-01-27T05:41:38.704Z"
    }
}
```

This endpoint shows your execution status and the inputs you provided, useful for confirming your request was processed correctly.

### Get Generation IDs

Once the execution is complete, retrieve the generation IDs in order to access your final outputs. A Blueprint can produce more than 1 Generation.

```bash
curl --request GET \
  --url https://cloud.leonardo.ai/api/rest/v1/blueprint-executions/YOUR_akUUID_HERE/generations \
  --header 'accept: application/json' \
  --header 'authorization: Bearer <YOUR_API_KEY>'
```

**Example Response:**

```json
{
    "blueprintExecutionGenerations": {
        "pageInfo": {
            "hasNextPage": false,
            "hasPreviousPage": false,
            "startCursor": "eyJjcmVhdGVkQXQiOiIyMDI2LTAxLTI3VDA1OjQxOjM4LjcwN1oiLCJha1VVSUQiOiI5MzU3MzljNy0wMGExLTQ3YTMtOTFiNi1kMGFkMzk4ZjY2YTcifQ==",
            "endCursor": "eyJjcmVhdGVkQXQiOiIyMDI2LTAxLTI3VDA1OjQxOjM4LjcwN1oiLCJha1VVSUQiOiI5MzU3MzljNy0wMGExLTQ3YTMtOTFiNi1kMGFkMzk4ZjY2YTcifQ=="
        },
        "edges": [
            {
                "cursor": "eyJjcmVhdGVkQXQiOiIyMDI2LTAxLTI3VDA1OjQxOjM4LjcwN1oiLCJha1VVSUQiOiI5MzU3MzljNy0wMGExLTQ3YTMtOTFiNi1kMGFkMzk4ZjY2YTcifQ==",
                "node": {
                    "akUUID": "8f04f1df-cc83-46da-b585-9d44a3b1dc0e",
                    "status": "COMPLETED",
                    "generationId": "YOUR_generationID_1_HERE",
                    "failedReason": null
                }
            },
						{
                "cursor": "eyJjcmVhdGVkQXQiOiIyMDI2LTAxLTI3VDA1OjQxOjM4LjcwN1oiLCJha1VVSUQiOiI5MzU3MzljNy0wMGExLTQ3YTMtOTFiNi1kMGFkMzk4ZjY2YTcifQ==",
                "node": {
                    "akUUID": "817bffec-d6f5-4ba0-8492-2de70d0eaf50",
                    "status": "COMPLETED",
                    "generationId": "YOUR_generationID_2_HERE",
                    "failedReason": null
                }
            }
        ]
    }
}
```

Save the `generationId` results to retrieve your final outputs in the next section.

***

## Getting Your Outputs

Once the Blueprint execution is complete, retrieve your generated assets.

### Retrieve Output Assets

Once the status is `COMPLETED`, use the `generationId` to fetch the final output via the normal [Get Generation](https://docs.leonardo.ai/reference/getgenerationbyid) endpoint. You should call this for each of the `generationId` returned from the Blueprint execution

```bash
curl --request GET \
  --url https://cloud.leonardo.ai/api/rest/v1/generations/YOUR_generationID_HERE \
  --header 'accept: application/json' \
  --header 'authorization: Bearer <YOUR_API_KEY>'
```

**Example Response:**

```json
{
    "generations_by_pk": {
        "generated_images": [
            {
                "url": "https://cdn.leonardo.ai/users/.../image.png",
                "nsfw": false,
                "id": YOUR_generationID_HERE,
                "likeCount": 0,
                "motionMP4URL": null,
                "generated_image_variation_generics": []
            }
        ],
        ...
    }
}
```

***

## Usage and Costs

Each Blueprint has its own cost based on its complexity and outputs. You can see the cost in the Blueprint Version response before executing.

**Cost Planning**

* Check `Cost` in the Blueprint Version response before executing

***

## Next Steps

* Explore all [50+ available Blueprints](https://app.leonardo.ai/blueprints) in the web app
* **Build your Own - Coming Soon!** Soon, you'll be able to build your own Blueprints. Turn your favourite creative processes into repeatable workflows.

***

## Need Help?

* Contact support using the in-app widget at the bottom right of the Leonardo web app