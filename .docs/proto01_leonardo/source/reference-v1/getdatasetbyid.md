---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Get a Single Dataset by ID

This endpoint gets the specific dataset

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
    "/datasets/{id}": {
      "get": {
        "tags": [
          "Dataset"
        ],
        "summary": "Get a Single Dataset by ID",
        "description": "This endpoint gets the specific dataset",
        "operationId": "getDatasetById",
        "parameters": [
          {
            "required": true,
            "description": "The ID of the dataset to return.",
            "in": "path",
            "name": "id",
            "schema": {
              "pattern": "[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89aAbB][a-f0-9]{3}-[a-f0-9]{12}",
              "type": "string"
            }
          }
        ],
        "responses": {
          "200": {
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "datasets_by_pk": {
                      "description": "columns and relationships of \"datasets\"",
                      "nullable": true,
                      "properties": {
                        "createdAt": {
                          "$ref": "#/components/schemas/timestamp"
                        },
                        "dataset_images": {
                          "items": {
                            "description": "columns and relationships of \"dataset_images\"",
                            "nullable": false,
                            "properties": {
                              "createdAt": {
                                "$ref": "#/components/schemas/timestamp"
                              },
                              "id": {
                                "$ref": "#/components/schemas/uuid"
                              },
                              "url": {
                                "nullable": false,
                                "title": "String",
                                "type": "string"
                              }
                            },
                            "title": "dataset_images",
                            "type": "object"
                          },
                          "nullable": false,
                          "type": "array"
                        },
                        "description": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        },
                        "id": {
                          "$ref": "#/components/schemas/uuid"
                        },
                        "name": {
                          "nullable": false,
                          "title": "String",
                          "type": "string"
                        },
                        "updatedAt": {
                          "$ref": "#/components/schemas/timestamp"
                        }
                      },
                      "title": "datasets",
                      "type": "object"
                    }
                  }
                }
              }
            },
            "description": "Responses for GET /datasets/{id}"
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "timestamp": {
        "type": "string",
        "nullable": false,
        "title": "timestamp"
      },
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