---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Create using Universal Upscaler

This endpoint will create a high resolution image using Universal Upscaler

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
    "/variations/universal-upscaler": {
      "post": {
        "tags": [
          "Variation"
        ],
        "summary": "Create using Universal Upscaler",
        "description": "This endpoint will create a high resolution image using Universal Upscaler",
        "operationId": "CreateUniversalUpscalerJob",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "properties": {
                  "creativityStrength": {
                    "nullable": true,
                    "title": "Int",
                    "type": "integer",
                    "default": 5,
                    "description": "The creativity strength of the universal upscaler. Must be between 1 and 10."
                  },
                  "detailContrast": {
                    "nullable": true,
                    "title": "Int",
                    "type": "integer",
                    "description": "The detail contrast of the universal upscaler. Must be between 1 and 10. Can only be used with ultraUpscaleStyle."
                  },
                  "generatedImageId": {
                    "nullable": true,
                    "title": "String",
                    "type": "string",
                    "description": "The ID of the generated image."
                  },
                  "initImageId": {
                    "nullable": true,
                    "title": "String",
                    "type": "string",
                    "description": "The ID of the init image uploaded."
                  },
                  "prompt": {
                    "nullable": true,
                    "title": "String",
                    "type": "string",
                    "description": "The prompt for the universal upscaler."
                  },
                  "similarity": {
                    "nullable": true,
                    "title": "Int",
                    "type": "integer",
                    "description": "The similarity of the universal upscaler. Must be between 1 and 10. Can only be used with ultraUpscaleStyle."
                  },
                  "ultraUpscaleStyle": {
                    "$ref": "#/components/schemas/universal_upscaler_ultra_style"
                  },
                  "upscaleMultiplier": {
                    "nullable": true,
                    "title": "Float",
                    "type": "number",
                    "default": 1.5,
                    "description": "The upscale multiplier of the universal upscaler. Must be between 1.0 and 2.0."
                  },
                  "upscalerStyle": {
                    "$ref": "#/components/schemas/universal_upscaler_style"
                  },
                  "variationId": {
                    "nullable": true,
                    "title": "String",
                    "type": "string",
                    "description": "The ID of the variation image."
                  }
                },
                "type": "object"
              }
            }
          },
          "description": "Query parameters are provided in the request body as a JSON object",
          "required": true
        },
        "responses": {
          "200": {
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "universalUpscaler": {
                      "properties": {
                        "id": {
                          "$ref": "#/components/schemas/uuid"
                        },
                        "apiCreditCost": {
                          "nullable": true,
                          "type": "integer",
                          "description": "API Credits Cost for Universal Upscaler Variation. Available for Production API Users. Note: it will be deprecated. Please use the cost instead.",
                          "deprecated": true
                        },
                        "cost": {
                          "$ref": "#/components/schemas/cost"
                        }
                      },
                      "title": "UniversalUpscalerOutput",
                      "type": "object"
                    }
                  }
                },
                "example": {
                  "universalUpscaler": {
                    "id": "g6h7i8j9-k0l1-m2n3-opqr-st5678901234",
                    "apiCreditCost": null,
                    "cost": {
                      "amount": "0.0147",
                      "unit": "DOLLARS"
                    }
                  }
                }
              }
            },
            "description": "Responses for POST /variations/universal-upscaler"
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
      },
      "universal_upscaler_style": {
        "type": "string",
        "nullable": true,
        "default": "GENERAL",
        "title": "universal_upscaler_style",
        "enum": [
          "GENERAL",
          "CINEMATIC",
          "2D ART & ILLUSTRATION",
          "CG ART & GAME ASSETS"
        ],
        "description": "The style to upscale images using universal upscaler with. Can not be used with ultraUpscaleStyle."
      },
      "universal_upscaler_ultra_style": {
        "type": "string",
        "nullable": true,
        "title": "universal_upscaler_ultra_style",
        "enum": [
          "ARTISTIC",
          "REALISTIC"
        ],
        "description": "The ultra style to upscale images using universal upscaler with. Can not be used with upscalerStyle."
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