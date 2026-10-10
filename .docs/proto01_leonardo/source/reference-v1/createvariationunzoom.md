---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Create unzoom

This endpoint will create an unzoom variation for the provided image ID

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
    "/variations/unzoom": {
      "post": {
        "tags": [
          "Variation"
        ],
        "summary": "Create unzoom",
        "description": "This endpoint will create an unzoom variation for the provided image ID",
        "operationId": "createVariationUnzoom",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "properties": {
                  "id": {
                    "nullable": false,
                    "title": "String",
                    "type": "string"
                  },
                  "isVariation": {
                    "nullable": true,
                    "title": "Boolean",
                    "type": "boolean"
                  }
                },
                "type": "object"
              }
            }
          },
          "description": "Query parameters can also be provided in the request body as a JSON object",
          "required": false
        },
        "responses": {
          "200": {
            "content": {
              "application/json": {
                "schema": {
                  "properties": {
                    "sdUnzoomJob": {
                      "nullable": true,
                      "properties": {
                        "id": {
                          "nullable": false,
                          "title": "String",
                          "type": "string"
                        },
                        "apiCreditCost": {
                          "nullable": true,
                          "type": "integer",
                          "description": "API Credits Cost for Unzoom Variation. Available for Production API Users. Note: it will be deprecated. Please use the cost instead.",
                          "deprecated": true
                        },
                        "cost": {
                          "$ref": "#/components/schemas/cost"
                        }
                      },
                      "title": "SDUnzoomOutput",
                      "type": "object"
                    }
                  }
                },
                "example": {
                  "sdUnzoomJob": {
                    "id": "c2d3e4f5-g6h7-8901-ijkl-mn2345678901",
                    "apiCreditCost": null,
                    "cost": {
                      "amount": "0.0147",
                      "unit": "DOLLARS"
                    }
                  }
                }
              }
            },
            "description": "Responses for POST /api/rest/v1/variations/unzoom"
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