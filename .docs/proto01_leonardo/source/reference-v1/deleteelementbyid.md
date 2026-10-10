---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Delete a Single Custom Element by ID

This endpoint will delete a specific custom model.

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
      "name": "Elements"
    }
  ],
  "paths": {
    "/elements/{id}": {
      "delete": {
        "tags": [
          "Elements"
        ],
        "summary": "Delete a Single Custom Element by ID",
        "description": "This endpoint will delete a specific custom model.",
        "operationId": "deleteElementById",
        "parameters": [
          {
            "required": true,
            "description": "The ID of the element to delete.",
            "in": "path",
            "name": "id",
            "schema": {
              "pattern": "[0-9]{*}",
              "type": "integer"
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
                    "delete_user_loras_by_pk": {
                      "description": "columns and relationships of \"user_loras\".",
                      "nullable": true,
                      "properties": {
                        "id": {
                          "nullable": false,
                          "title": "Int",
                          "type": "integer"
                        }
                      },
                      "title": "user_loras",
                      "type": "object"
                    }
                  }
                }
              }
            },
            "description": "Responses for DELETE /models/{id}"
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