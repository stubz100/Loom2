---
updatedAt: 2026-04-21T23:42:41.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Delete uploaded media

This endpoint deletes an uploaded media record and removes the associated file from S3

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
      "name": "Media"
    }
  ],
  "paths": {
    "/media/{id}": {
      "delete": {
        "tags": [
          "Media"
        ],
        "summary": "Delete uploaded media",
        "description": "This endpoint deletes an uploaded media record and removes the associated file from S3",
        "operationId": "deleteUploadedMediaById",
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
                    "delete_uploaded_media_by_pk": {
                      "nullable": true,
                      "properties": {
                        "id": {
                          "nullable": true,
                          "title": "uuid",
                          "type": "string"
                        }
                      },
                      "title": "uploaded_media",
                      "type": "object"
                    }
                  }
                }
              }
            },
            "description": "Responses for DELETE /media/{id}"
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