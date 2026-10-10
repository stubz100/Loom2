---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Delete a Single Custom Model by ID

This endpoint will delete a specific custom model

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
    "/models/{id}": {
      "delete": {
        "tags": [
          "Models"
        ],
        "summary": "Delete a Single Custom Model by ID",
        "description": "This endpoint will delete a specific custom model",
        "operationId": "deleteModelById",
        "parameters": [
          {
            "required": true,
            "description": "The ID of the model to delete.",
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
                    "delete_custom_models_by_pk": {
                      "description": "columns and relationships of \"custom_models\"",
                      "nullable": true,
                      "properties": {
                        "id": {
                          "$ref": "#/components/schemas/uuid"
                        }
                      },
                      "title": "custom_models",
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