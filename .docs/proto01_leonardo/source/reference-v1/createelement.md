---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Train a Custom Element

This endpoint will train a new custom element.

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
    "/elements": {
      "post": {
        "tags": [
          "Elements"
        ],
        "summary": "Train a Custom Element",
        "description": "This endpoint will train a new custom element.",
        "operationId": "createElement",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "properties": {
                  "name": {
                    "default": "placeholder",
                    "nullable": false,
                    "title": "String",
                    "type": "string",
                    "description": "The name of the element."
                  },
                  "description": {
                    "default": "",
                    "nullable": true,
                    "title": "String",
                    "type": "string",
                    "description": "The description of the element."
                  },
                  "datasetId": {
                    "default": "",
                    "nullable": false,
                    "title": "String",
                    "type": "string",
                    "description": "The ID of the dataset to train the element on."
                  },
                  "instance_prompt": {
                    "default": "",
                    "nullable": true,
                    "title": "String",
                    "type": "string",
                    "description": "Use a word that is closely related to what you're training that isn't too common. For example, instead of 'dog,' try something unique like 'jackthedog' or 'magicdonut'. Required for all non-FLUX_DEV models and FLUX_DEV Character model training."
                  },
                  "lora_focus": {
                    "nullable": false,
                    "title": "String",
                    "type": "string",
                    "description": "The category determines how the element will be trained. Options are 'General' | 'Character' | 'Style' | 'Object'. FLUX_DEV doesn't support General category."
                  },
                  "train_text_encoder": {
                    "default": true,
                    "nullable": false,
                    "title": "Boolean",
                    "type": "boolean",
                    "description": "Whether or not encode the train text."
                  },
                  "resolution": {
                    "default": 1024,
                    "nullable": true,
                    "title": "Int",
                    "type": "integer",
                    "description": "The resolution for training. Must be 1024."
                  },
                  "sd_version": {
                    "nullable": false,
                    "default": "FLUX_DEV",
                    "title": "sd_versions",
                    "enum": [
                      "SDXL_0_9",
                      "SDXL_1_0",
                      "LEONARDO_DIFFUSION_XL",
                      "LEONARDO_LIGHTNING_XL",
                      "VISION_XL",
                      "KINO_XL",
                      "ALBEDO_XL",
                      "FLUX_DEV"
                    ],
                    "description": "The base version to use if not using a custom model."
                  },
                  "num_train_epochs": {
                    "nullable": false,
                    "title": "Int",
                    "type": "integer",
                    "description": "The number of times the entire training dataset is passed through the element.<br><br><table><tr><th>Model Type</th><th>Lora Focus</th><th>Min</th><th>Max</th><th>Default</th></tr><tr><td>Default</td><td>General | Style | Character | Object</td><td>1</td><td>250</td><td>100</td></tr><tr><td rowspan='3'>FLUX_DEV</td><td>Style</td><td>30</td><td>120</td><td>60</td></tr><tr><td>Object</td><td>120</td><td>220</td><td>140</td></tr><tr><td>Character</td><td>100</td><td>200</td><td>135</td></tr><tr><td>General</td><td colspan='3'>NA</td></tr></table>"
                  },
                  "learning_rate": {
                    "nullable": false,
                    "title": "Float",
                    "type": "number",
                    "description": "The speed at which the model learns during training.<br><br><table><tr><th>Model Type</th><th>Lora Focus</th><th>Min</th><th>Max</th><th>Default</th></tr><tr><td>Default</td><td>General | Style | Character | Object</td><td>0.00000001</td><td>0.00001</td><td>0.000001</td></tr><tr><td rowspan='3'>FLUX_DEV</td><td>Style</td><td>0.000001</td><td>0.00003</td><td>0.00001</td></tr><tr><td>Object</td><td>0.00001</td><td>0.001</td><td>0.0004</td></tr><tr><td>Character</td><td>0.00001</td><td>0.001</td><td>0.0005</td></tr><tr><td>General</td><td colspan='3'>NA</td></tr></table>"
                  }
                },
                "required": [
                  "name",
                  "datasetId",
                  "lora_focus",
                  "sd_version",
                  "learning_rate",
                  "num_train_epochs",
                  "train_text_encoder"
                ],
                "type": "object"
              }
            }
          },
          "description": "Query parameters to be provided in the request body as a JSON object.",
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
                        "userLoraId": {
                          "nullable": false,
                          "title": "Int",
                          "type": "integer"
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
                    "userLoraId": 123456,
                    "apiCreditCost": null,
                    "cost": {
                      "amount": "0.0147",
                      "unit": "DOLLARS"
                    }
                  }
                }
              }
            },
            "description": "Responses for POST /elements."
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