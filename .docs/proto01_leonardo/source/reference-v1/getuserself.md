---
updatedAt: 2026-06-03T21:44:56.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Get user information

This endpoint will return your user information such as your user id, username, token renewal date and current amounts of the following: subscription tokens, gpt (prompt generation) tokens, and model training tokens

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
      "name": "User"
    }
  ],
  "paths": {
    "/me": {
      "get": {
        "tags": [
          "User"
        ],
        "summary": "Get user information",
        "description": "This endpoint will return your user information such as your user id, username, token renewal date and current amounts of the following: subscription tokens, gpt (prompt generation) tokens, and model training tokens",
        "operationId": "getUserSelf",
        "responses": {
          "200": {
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "user_details": {
                      "items": {
                        "description": "columns and relationships of \"user_details\"",
                        "nullable": false,
                        "properties": {
                          "user": {
                            "description": "columns and relationships of \"users\"",
                            "nullable": true,
                            "properties": {
                              "id": {
                                "$ref": "#/components/schemas/uuid"
                              },
                              "username": {
                                "nullable": true,
                                "title": "String",
                                "type": "string",
                                "description": "Username of the user."
                              }
                            },
                            "title": "users",
                            "type": "object"
                          },
                          "tokenRenewalDate": {
                            "nullable": true,
                            "title": "timestamp",
                            "type": "string",
                            "description": "User Plan Token Renewal Date."
                          },
                          "paidTokens": {
                            "nullable": true,
                            "title": "Int",
                            "type": "integer",
                            "description": "Current balance of paid tokens the user has."
                          },
                          "subscriptionTokens": {
                            "nullable": false,
                            "title": "Int",
                            "type": "integer",
                            "description": "Current balance of user plan subscription tokens the user has."
                          },
                          "subscriptionGptTokens": {
                            "nullable": false,
                            "title": "Int",
                            "type": "integer",
                            "description": "Current balance of user plan GPT tokens the user has."
                          },
                          "subscriptionModelTokens": {
                            "nullable": false,
                            "title": "Int",
                            "type": "integer",
                            "description": "Current balance of model training tokens the user has."
                          },
                          "apiConcurrencySlots": {
                            "nullable": false,
                            "title": "Int",
                            "type": "integer",
                            "description": "API Concurrency Slots."
                          },
                          "apiPaidTokens": {
                            "nullable": true,
                            "title": "Int",
                            "type": "integer",
                            "description": "Current balance of API paid tokens the user has."
                          },
                          "apiSubscriptionTokens": {
                            "nullable": false,
                            "title": "Int",
                            "type": "integer",
                            "description": "Current balance of Enterprise API subscriptions tokens the user has."
                          },
                          "apiPlanTokenRenewalDate": {
                            "nullable": true,
                            "title": "timestamp",
                            "type": "string",
                            "description": "API Plan Token Renewal Date."
                          }
                        },
                        "title": "user_details",
                        "type": "object"
                      },
                      "nullable": false,
                      "type": "array"
                    }
                  }
                }
              }
            },
            "description": "Responses for GET /me"
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
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