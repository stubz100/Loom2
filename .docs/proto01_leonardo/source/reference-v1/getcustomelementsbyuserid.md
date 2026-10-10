---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Get a list of Custom Elements by User ID

This endpoint gets the list of custom elements belongs to the user.

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
    "/elements/user/{userId}": {
      "get": {
        "tags": [
          "Elements"
        ],
        "summary": "Get a list of Custom Elements by User ID",
        "description": "This endpoint gets the list of custom elements belongs to the user.",
        "operationId": "getCustomElementsByUserId",
        "parameters": [
          {
            "required": true,
            "description": "The ID of the user to return.",
            "in": "path",
            "name": "userId",
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
                  "properties": {
                    "user_loras": {
                      "items": {
                        "description": "columns and relationships of \"user_loras\".",
                        "nullable": true,
                        "title": "user_loras",
                        "type": "object",
                        "properties": {
                          "createdAt": {
                            "$ref": "#/components/schemas/timestamp"
                          },
                          "description": {
                            "nullable": false,
                            "title": "String",
                            "type": "string"
                          },
                          "id": {
                            "nullable": false,
                            "title": "Int",
                            "type": "integer"
                          },
                          "instancePrompt": {
                            "nullable": true,
                            "title": "String",
                            "type": "string"
                          },
                          "resolution": {
                            "nullable": false,
                            "title": "Int",
                            "type": "integer"
                          },
                          "learningRate": {
                            "nullable": false,
                            "title": "Float",
                            "type": "number"
                          },
                          "trainingEpoch": {
                            "nullable": false,
                            "title": "Int",
                            "type": "integer"
                          },
                          "name": {
                            "nullable": false,
                            "title": "String",
                            "type": "string"
                          },
                          "trainTextEncoder": {
                            "nullable": false,
                            "title": "Boolean",
                            "type": "boolean"
                          },
                          "baseModel": {
                            "nullable": false,
                            "title": "String",
                            "type": "string"
                          },
                          "status": {
                            "$ref": "#/components/schemas/job_status"
                          },
                          "focus": {
                            "nullable": false,
                            "title": "String",
                            "type": "string"
                          },
                          "updatedAt": {
                            "$ref": "#/components/schemas/timestamp"
                          }
                        }
                      },
                      "nullable": true,
                      "type": "array"
                    }
                  }
                }
              }
            },
            "description": "Responses for GET /elements/user/{userId}."
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
      "timestamp": {
        "type": "string",
        "nullable": false,
        "title": "timestamp"
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