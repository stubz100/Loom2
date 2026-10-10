---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Get a Single Custom Element by ID

This endpoint gets the specific custom element.

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
      "get": {
        "tags": [
          "Elements"
        ],
        "summary": "Get a Single Custom Element by ID",
        "description": "This endpoint gets the specific custom element.",
        "operationId": "getElementById",
        "parameters": [
          {
            "required": true,
            "description": "The ID of the custom element to return.",
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
                    "user_loras_by_pk": {
                      "description": "columns and relationships of \"user_loras\".",
                      "nullable": true,
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
                      },
                      "title": "user_loras",
                      "type": "object"
                    }
                  }
                }
              }
            },
            "description": "Responses for GET /elements/{id}."
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