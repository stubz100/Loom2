---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Improve a Prompt

This endpoint returns a improved prompt

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
      "name": "Prompt"
    }
  ],
  "paths": {
    "/prompt/improve": {
      "post": {
        "tags": [
          "Prompt"
        ],
        "summary": "Improve a Prompt",
        "description": "This endpoint returns a improved prompt",
        "operationId": "promptImprove",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "properties": {
                  "prompt": {
                    "nullable": false,
                    "title": "String",
                    "type": "string",
                    "description": "The prompt to improve."
                  },
                  "promptInstructions": {
                    "nullable": true,
                    "title": "String",
                    "type": "string",
                    "description": "The prompt is improved based on the given instructions."
                  },
                  "isVideo": {
                    "type": "boolean",
                    "description": "Specifies whether the prompt is for a video generation. Defaults to false (image prompt).",
                    "nullable": true,
                    "example": true
                  }
                },
                "required": [
                  "prompt"
                ],
                "type": "object"
              }
            }
          },
          "description": "Query parameters to be provided in the request body as a JSON object",
          "required": true
        },
        "responses": {
          "200": {
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "promptGeneration": {
                      "nullable": false,
                      "properties": {
                        "prompt": {
                          "nullable": false,
                          "title": "String",
                          "type": "string",
                          "description": "The improved prompt.",
                          "default": "The improved prompt."
                        },
                        "apiCreditCost": {
                          "nullable": false,
                          "type": "integer",
                          "description": "API Credits Cost for Random Prompt Generation. Available for Production API Users. Note: it will be deprecated. Please use the cost instead.",
                          "default": 4,
                          "deprecated": true
                        },
                        "cost": {
                          "$ref": "#/components/schemas/cost"
                        }
                      },
                      "title": "promptGenerationOutput",
                      "type": "object"
                    }
                  }
                },
                "example": {
                  "promptGeneration": {
                    "prompt": "A majestic dragon soaring through dramatic stormy clouds, photorealistic, cinematic lighting, 8k ultra detailed",
                    "apiCreditCost": null,
                    "cost": {
                      "amount": "0.0147",
                      "unit": "DOLLARS"
                    }
                  }
                }
              }
            },
            "description": "Responses for POST /prompt/improve"
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "cost": {
        "nullable": true,
        "type": "object",
        "title": "Cost",
        "description": "The cost of the operation.",
        "properties": {
          "amount": {
            "type": "string",
            "description": "The amount of the cost."
          },
          "unit": {
            "type": "string",
            "enum": [
              "CREDITS",
              "DOLLARS"
            ],
            "description": "The unit of the cost. Can be CREDITS or DOLLARS. Note: DOLLARS unit only supports PAYG plan."
          }
        }
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