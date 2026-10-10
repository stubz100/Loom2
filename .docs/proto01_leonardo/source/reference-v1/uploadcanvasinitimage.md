---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Upload Canvas Editor init and mask image

This endpoint returns presigned details to upload an init image and a mask image to S3

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
    "/canvas-init-image": {
      "post": {
        "tags": [
          "Init Images"
        ],
        "summary": "Upload Canvas Editor init and mask image",
        "description": "This endpoint returns presigned details to upload an init image and a mask image to S3",
        "operationId": "uploadCanvasInitImage",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "properties": {
                  "initExtension": {
                    "nullable": false,
                    "title": "String",
                    "type": "string",
                    "description": "Has to be png, jpg, jpeg, or webp."
                  },
                  "maskExtension": {
                    "nullable": false,
                    "title": "String",
                    "type": "string",
                    "description": "Has to be png, jpg, jpeg, or webp."
                  }
                },
                "required": [
                  "initExtension",
                  "maskExtension"
                ],
                "type": "object"
              }
            }
          },
          "description": "Query parameters provided in the request body as a JSON object",
          "required": true
        },
        "responses": {
          "200": {
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "uploadCanvasInitImage": {
                      "nullable": true,
                      "properties": {
                        "initImageId": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        },
                        "initFields": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        },
                        "initKey": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        },
                        "initUrl": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        },
                        "maskImageId": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        },
                        "maskFields": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        },
                        "maskKey": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        },
                        "maskUrl": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        }
                      },
                      "title": "CanvasInitImageUploadOutput",
                      "type": "object"
                    }
                  }
                }
              }
            },
            "description": "Responses for POST /canvas-init-image"
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