---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Get single init image

This endpoint will return a single init image

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
      "name": "Init Images"
    }
  ],
  "paths": {
    "/init-image/{id}": {
      "get": {
        "tags": [
          "Init Images"
        ],
        "summary": "Get single init image",
        "description": "This endpoint will return a single init image",
        "operationId": "getInitImageById",
        "parameters": [
          {
            "required": true,
            "description": "_\"id\" is required_",
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
                    "init_images_by_pk": {
                      "description": "columns and relationships of \"init_images\"",
                      "nullable": true,
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
                      "title": "init_images",
                      "type": "object"
                    }
                  }
                }
              }
            },
            "description": "Responses for GET /init-image/{id}"
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