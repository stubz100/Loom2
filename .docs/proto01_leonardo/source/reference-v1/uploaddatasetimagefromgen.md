---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Upload a Single Generated Image to a Dataset

This endpoint will upload a previously generated image to the dataset

# OpenAPI definition

```json
{
  "openapi": "3.0.0",
  "info": {
    "description": "Leonardo.Ai API OpenAPI specification (v1.0).",
    "title": "Rest Endpoints",
    "version": "v1.0.0"
  },
  "servers": [
    {
      "url": "https://cloud.leonardo.ai/api/rest/v1",
      "description": "Leonardo.Ai API server"
    }
  ],
  "tags": [
    {
      "name": "Dataset"
    }
  ],
  "paths": {
    "/datasets/{datasetId}/upload/gen": {
      "post": {
        "tags": [
          "Dataset"
        ],
        "summary": "Upload a Single Generated Image to a Dataset",
        "description": "This endpoint will upload a previously generated image to the dataset",
        "operationId": "uploadDatasetImageFromGen",
        "parameters": [
          {
            "required": true,
            "description": "The ID of the dataset to upload the image to.",
            "in": "path",
            "name": "datasetId",
            "schema": {
              "type": "string"
            }
          }
        ],
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "properties": {
                  "generatedImageId": {
                    "nullable": false,
                    "title": "String",
                    "type": "string",
                    "description": "The ID of the image to upload to the dataset."
                  }
                },
                "required": [
                  "generatedImageId"
                ],
                "type": "object"
              }
            }
          },
          "description": "Query parameters to be provided in the request body as a JSON object",
          "required": true
        },
        "responses": {
          "200": {
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "uploadDatasetImageFromGen": {
                      "nullable": true,
                      "properties": {
                        "id": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        }
                      },
                      "title": "DatasetGenUploadOutput",
                      "type": "object"
                    }
                  }
                }
              }
            },
            "description": "Responses for POST /datasets/{datasetId}/upload/gen"
          }
        }
      }
    }
  },
  "components": {
    "securitySchemes": {
      "bearerAuth": {
        "type": "http",
        "bearerFormat": "auth-scheme",
        "description": "Bearer HTTP authentication. Allowed headers `Authorization: Bearer <api_key>`",
        "scheme": "bearer"
      }
    }
  },
  "security": [
    {
      "bearerAuth": []
    }
  ]
}
```