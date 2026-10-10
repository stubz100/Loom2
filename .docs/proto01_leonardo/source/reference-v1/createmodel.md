---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Train a Custom Model

This endpoint will train a new custom model

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
      "name": "Models"
    }
  ],
  "paths": {
    "/models": {
      "post": {
        "tags": [
          "Models"
        ],
        "summary": "Train a Custom Model",
        "description": "This endpoint will train a new custom model",
        "operationId": "createModel",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "properties": {
                  "name": {
                    "nullable": false,
                    "title": "String",
                    "type": "string",
                    "description": "The name of the model."
                  },
                  "description": {
                    "default": "",
                    "nullable": true,
                    "title": "String",
                    "type": "string",
                    "description": "The description of the model."
                  },
                  "datasetId": {
                    "nullable": false,
                    "title": "String",
                    "type": "string",
                    "description": "The ID of the dataset to train the model on."
                  },
                  "instance_prompt": {
                    "nullable": false,
                    "title": "String",
                    "type": "string",
                    "description": "The instance prompt to use during training."
                  },
                  "modelType": {
                    "$ref": "#/components/schemas/custom_model_type"
                  },
                  "nsfw": {
                    "default": false,
                    "nullable": true,
                    "title": "Boolean",
                    "type": "boolean",
                    "description": "Whether or not the model is NSFW."
                  },
                  "resolution": {
                    "default": 512,
                    "nullable": true,
                    "title": "Int",
                    "type": "integer",
                    "description": "The resolution for training. Must be 512 or 768."
                  },
                  "sd_version": {
                    "nullable": true,
                    "title": "sd_versions",
                    "enum": [
                      "v1_5",
                      "v2"
                    ],
                    "description": "The base version of stable diffusion to use if not using a custom model. v1_5 is 1.5, v2 is 2.1, if not specified it will default to v1_5."
                  },
                  "strength": {
                    "$ref": "#/components/schemas/strength"
                  }
                },
                "required": [
                  "name",
                  "datasetId",
                  "instance_prompt"
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
                    "sdTrainingJob": {
                      "nullable": true,
                      "properties": {
                        "customModelId": {
                          "nullable": false,
                          "title": "String",
                          "type": "string"
                        },
                        "apiCreditCost": {
                          "nullable": true,
                          "type": "integer",
                          "description": "API Credits Cost for Model Training. Available for Production API Users. Note: it will be deprecated. Please use the cost instead.",
                          "deprecated": true
                        },
                        "cost": {
                          "$ref": "#/components/schemas/cost"
                        }
                      },
                      "title": "SDTrainingOutput",
                      "type": "object"
                    }
                  }
                },
                "example": {
                  "sdTrainingJob": {
                    "customModelId": "m2n3o4p5-q6r7-s8t9-uvwx-yz1234567890",
                    "apiCreditCost": null,
                    "cost": {
                      "amount": "0.0147",
                      "unit": "DOLLARS"
                    }
                  }
                }
              }
            },
            "description": "Responses for POST /models"
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
      "strength": {
        "type": "string",
        "nullable": false,
        "title": "strength",
        "enum": [
          "VERY_LOW",
          "LOW",
          "MEDIUM",
          "HIGH"
        ],
        "description": "When training using the PIXEL_ART model type, this influences the training strength.",
        "default": "MEDIUM"
      },
      "custom_model_type": {
        "type": "string",
        "default": "GENERAL",
        "nullable": false,
        "title": "custom_model_type",
        "enum": [
          "GENERAL",
          "BUILDINGS",
          "CHARACTERS",
          "ENVIRONMENTS",
          "FASHION",
          "ILLUSTRATIONS",
          "GAME_ITEMS",
          "GRAPHICAL_ELEMENTS",
          "PHOTOGRAPHY",
          "PIXEL_ART",
          "PRODUCT_DESIGN",
          "TEXTURES",
          "UI_ELEMENTS",
          "VECTOR"
        ],
        "description": "The category the most accurately reflects the model."
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