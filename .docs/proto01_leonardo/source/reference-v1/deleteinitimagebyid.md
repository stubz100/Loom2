---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Delete init image

This endpoint deletes an init image

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
      "delete": {
        "tags": [
          "Init Images"
        ],
        "summary": "Delete init image",
        "description": "This endpoint deletes an init image",
        "operationId": "deleteInitImageById",
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
                    "delete_init_images_by_pk": {
                      "description": "columns and relationships of \"init_images\"",
                      "nullable": true,
                      "properties": {
                        "id": {
                          "$ref": "#/components/schemas/uuid"
                        }
                      },
                      "title": "init_images",
                      "type": "object"
                    }
                  }
                }
              }
            },
            "description": "Responses for DELETE /init-image/{id}"
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