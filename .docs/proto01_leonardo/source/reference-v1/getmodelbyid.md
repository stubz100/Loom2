---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Get a Single Custom Model by ID

This endpoint gets the specific custom model

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
    "/models/{id}": {
      "get": {
        "tags": [
          "Models"
        ],
        "summary": "Get a Single Custom Model by ID",
        "description": "This endpoint gets the specific custom model",
        "operationId": "getModelById",
        "parameters": [
          {
            "required": true,
            "description": "The ID of the custom model to return.",
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
                    "custom_models_by_pk": {
                      "description": "columns and relationships of \"custom_models\"",
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
                          "$ref": "#/components/schemas/uuid"
                        },
                        "instancePrompt": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        },
                        "modelHeight": {
                          "nullable": false,
                          "title": "Int",
                          "type": "integer"
                        },
                        "modelWidth": {
                          "nullable": false,
                          "title": "Int",
                          "type": "integer"
                        },
                        "name": {
                          "nullable": false,
                          "title": "String",
                          "type": "string"
                        },
                        "public": {
                          "nullable": false,
                          "title": "Boolean",
                          "type": "boolean"
                        },
                        "sdVersion": {
                          "$ref": "#/components/schemas/sd_versions"
                        },
                        "status": {
                          "$ref": "#/components/schemas/job_status"
                        },
                        "type": {
                          "$ref": "#/components/schemas/custom_model_type"
                        },
                        "updatedAt": {
                          "$ref": "#/components/schemas/timestamp"
                        }
                      },
                      "title": "custom_models",
                      "type": "object"
                    }
                  }
                }
              }
            },
            "description": "Responses for GET /models/{id}"
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "sd_versions": {
        "type": "string",
        "nullable": false,
        "title": "sd_versions",
        "enum": [
          "v1_5",
          "v2",
          "v3",
          "SDXL_0_8",
          "SDXL_0_9",
          "SDXL_1_0",
          "SDXL_LIGHTNING",
          "PHOENIX",
          "FLUX",
          "FLUX_DEV",
          "KINO_2_0"
        ],
        "description": "The base version of stable diffusion to use if not using a custom model. v1_5 is 1.5, v2 is 2.1, if not specified it will default to v1_5. Also includes SDXL and SDXL Lightning models"
      },
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