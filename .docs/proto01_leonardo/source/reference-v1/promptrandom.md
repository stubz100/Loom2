---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Generate a Random prompt

This endpoint returns a random prompt

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
    "/prompt/random": {
      "post": {
        "tags": [
          "Prompt"
        ],
        "summary": "Generate a Random prompt",
        "description": "This endpoint returns a random prompt",
        "operationId": "promptRandom",
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
                          "description": "The random prompt generated.",
                          "default": "The random prompt generated."
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
                    "prompt": "A majestic dragon soaring through stormy clouds",
                    "apiCreditCost": null,
                    "cost": {
                      "amount": "0.0147",
                      "unit": "DOLLARS"
                    }
                  }
                }
              }
            },
            "description": "Responses for POST /prompt/random"
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