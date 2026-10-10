---
updatedAt: 2026-04-21T23:42:41.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Get uploaded media

This endpoint returns details of an uploaded media record

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
      "get": {
        "tags": [
          "Media"
        ],
        "summary": "Get uploaded media",
        "description": "This endpoint returns details of an uploaded media record",
        "operationId": "getUploadedMediaById",
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
                    "uploaded_media_by_pk": {
                      "nullable": true,
                      "properties": {
                        "id": {
                          "nullable": true,
                          "title": "uuid",
                          "type": "string"
                        },
                        "createdAt": {
                          "nullable": true,
                          "title": "timestamp",
                          "type": "string"
                        },
                        "url": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        },
                        "thumbnailUrl": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        },
                        "status": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        },
                        "statusReason": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        },
                        "mediaType": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        },
                        "duration": {
                          "nullable": true,
                          "title": "Float",
                          "type": "number"
                        },
                        "width": {
                          "nullable": true,
                          "title": "Int",
                          "type": "integer"
                        },
                        "height": {
                          "nullable": true,
                          "title": "Int",
                          "type": "integer"
                        },
                        "video_fps": {
                          "nullable": true,
                          "title": "Float",
                          "type": "number"
                        }
                      },
                      "title": "uploaded_media",
                      "type": "object"
                    }
                  }
                }
              }
            },
            "description": "Responses for GET /media/{id}"
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