---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Get motion variation by ID

This endpoint will get the motion variation by ID

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
      "name": "Variation"
    }
  ],
  "paths": {
    "/motion-variations/{id}": {
      "get": {
        "tags": [
          "Variation"
        ],
        "summary": "Get motion variation by ID",
        "description": "This endpoint will get the motion variation by ID",
        "operationId": "getMotionVariationById",
        "parameters": [
          {
            "required": true,
            "description": "\"id\" is required",
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
                    "generated_image_variation_motion": {
                      "items": {
                        "description": "columns and relationships of \"generated_image_variation_motion\"",
                        "nullable": false,
                        "properties": {
                          "createdAt": {
                            "$ref": "#/components/schemas/timestamp"
                          },
                          "id": {
                            "$ref": "#/components/schemas/uuid"
                          },
                          "status": {
                            "$ref": "#/components/schemas/job_status"
                          },
                          "motionTransformType": {
                            "$ref": "#/components/schemas/MOTION_VARIATION_TYPE"
                          },
                          "resolution": {
                            "$ref": "#/components/schemas/MOTION_RESOLUTION"
                          },
                          "url": {
                            "nullable": true,
                            "title": "String",
                            "type": "string"
                          }
                        },
                        "title": "generated_image_variation_motion",
                        "type": "object"
                      },
                      "nullable": false,
                      "type": "array"
                    }
                  }
                }
              }
            },
            "description": "Responses for GET /motion-variations/{id}"
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "job_status": {
        "type": "string",
        "nullable": false,
        "title": "job_status",
        "enum": [
          "PENDING",
          "COMPLETE",
          "FAILED"
        ],
        "description": "The status of the current task."
      },
      "MOTION_VARIATION_TYPE": {
        "type": "string",
        "nullable": false,
        "title": "MOTION_VARIATION_TYPE",
        "enum": [
          "UPSCALE"
        ],
        "description": "The type of motion variation."
      },
      "MOTION_RESOLUTION": {
        "type": "string",
        "nullable": false,
        "title": "MOTION_RESOLUTION",
        "enum": [
          "RESOLUTION_720"
        ],
        "description": "The resolution of the upscaled video. RESOLUTION_720 is the only option for now."
      },
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