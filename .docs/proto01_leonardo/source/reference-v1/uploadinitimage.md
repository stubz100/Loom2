---
updatedAt: 2026-06-03T21:44:56.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Upload init image

This endpoint returns presigned details to upload an init image to S3

Detailed instructions for using this endpoint are available in the guide:  [How to upload an image using a presigned URL](https://docs.leonardo.ai/docs/how-to-upload-an-image-using-a-presigned-url).

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
    "/init-image": {
      "post": {
        "tags": [
          "Init Images"
        ],
        "summary": "Upload init image",
        "description": "This endpoint returns presigned details to upload an init image to S3",
        "operationId": "uploadInitImage",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "properties": {
                  "extension": {
                    "nullable": false,
                    "title": "String",
                    "type": "string",
                    "description": "Has to be png, jpg, jpeg, or webp."
                  }
                },
                "required": [
                  "extension"
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
                    "uploadInitImage": {
                      "nullable": true,
                      "properties": {
                        "fields": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        },
                        "id": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        },
                        "key": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        },
                        "url": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        }
                      },
                      "title": "InitImageUploadOutput",
                      "type": "object"
                    }
                  }
                }
              }
            },
            "description": "Responses for POST /init-image"
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