---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Create a Dataset

This endpoint creates a new dataset

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
    "/datasets": {
      "post": {
        "tags": [
          "Dataset"
        ],
        "summary": "Create a Dataset",
        "description": "This endpoint creates a new dataset",
        "operationId": "createDataset",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "properties": {
                  "name": {
                    "nullable": false,
                    "title": "String",
                    "type": "string",
                    "description": "The name of the dataset."
                  },
                  "description": {
                    "nullable": true,
                    "title": "String",
                    "type": "string",
                    "description": "A description for the dataset."
                  }
                },
                "required": [
                  "name"
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
                    "insert_datasets_one": {
                      "description": "columns and relationships of \"datasets\"",
                      "nullable": true,
                      "properties": {
                        "id": {
                          "$ref": "#/components/schemas/uuid"
                        }
                      },
                      "title": "datasets",
                      "type": "object"
                    }
                  }
                }
              }
            },
            "description": "Responses for POST /datasets"
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "uuid": {
        "nullable": true,
        "pattern": "[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89aAbB][a-f0-9]{3}-[a-f0-9]{12}",
        "title": "uuid",
        "type": "string"
      }
    },
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