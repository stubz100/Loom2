---
updatedAt: 2026-04-21T23:42:41.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Upload media

This endpoint returns presigned POST credentials to upload a video or audio file directly to S3.

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
    "/media": {
      "post": {
        "tags": [
          "Media"
        ],
        "summary": "Upload media",
        "description": "This endpoint returns presigned POST credentials to upload a video or audio file directly to S3.",
        "operationId": "uploadMedia",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "properties": {
                  "extension": {
                    "nullable": false,
                    "title": "String",
                    "type": "string",
                    "description": "The file extension of the media file to upload. Supported extensions for video: `mp4`, `mov`. Supported for audio: `mp3`, `wav`."
                  },
                  "originalFilename": {
                    "nullable": true,
                    "title": "String",
                    "type": "string",
                    "description": "Original file name for display. Required for audio uploads (`mp3`, `wav`). Optional for video."
                  },
                  "teamId": {
                    "nullable": true,
                    "title": "String",
                    "type": "string",
                    "description": "Optional team UUID. When set, the upload is associated with that team and the caller must be a member."
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
                    "uploadMedia": {
                      "nullable": true,
                      "properties": {
                        "uploadId": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        },
                        "url": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        },
                        "fields": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        }
                      },
                      "title": "MediaUploadOutput",
                      "type": "object"
                    }
                  }
                }
              }
            },
            "description": "Responses for POST /media"
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