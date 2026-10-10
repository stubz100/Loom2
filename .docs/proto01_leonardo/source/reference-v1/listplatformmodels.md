---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# List Platform Models

Get a list of public Platform Models available for use with generations.

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
      "name": "Models"
    }
  ],
  "paths": {
    "/platformModels": {
      "get": {
        "tags": [
          "Models"
        ],
        "parameters": [],
        "summary": "List Platform Models",
        "description": "Get a list of public Platform Models available for use with generations.",
        "operationId": "listPlatformModels",
        "responses": {
          "200": {
            "content": {
              "application/json": {
                "schema": {
                  "properties": {
                    "custom_models": {
                      "items": {
                        "description": "columns and relationships of \"custom_models\"",
                        "nullable": false,
                        "properties": {
                          "description": {
                            "nullable": false,
                            "title": "String",
                            "type": "string"
                          },
                          "featured": {
                            "nullable": false,
                            "title": "Boolean",
                            "type": "boolean"
                          },
                          "generated_image": {
                            "description": "columns and relationships of \"generated_images\"",
                            "nullable": true,
                            "properties": {
                              "id": {
                                "$ref": "#/components/schemas/uuid"
                              },
                              "url": {
                                "nullable": false,
                                "title": "String",
                                "type": "string"
                              }
                            },
                            "title": "generated_images",
                            "type": "object"
                          },
                          "id": {
                            "$ref": "#/components/schemas/uuid"
                          },
                          "name": {
                            "nullable": false,
                            "title": "String",
                            "type": "string"
                          },
                          "nsfw": {
                            "nullable": false,
                            "title": "Boolean",
                            "type": "boolean"
                          }
                        },
                        "title": "custom_models",
                        "type": "object"
                      },
                      "nullable": false,
                      "type": "array"
                    }
                  }
                }
              }
            },
            "description": "Responses for GET /api/rest/v1/platformModels"
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