---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# List Elements

Get a list of public Elements available for use with generations.

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
      "get": {
        "tags": [
          "Elements"
        ],
        "summary": "List Elements",
        "description": "Get a list of public Elements available for use with generations.",
        "operationId": "listElements",
        "responses": {
          "200": {
            "content": {
              "application/json": {
                "schema": {
                  "properties": {
                    "loras": {
                      "items": {
                        "description": "columns and relationships of \"elements\".",
                        "nullable": false,
                        "properties": {
                          "akUUID": {
                            "$ref": "#/components/schemas/lora/properties/akUUID"
                          },
                          "baseModel": {
                            "$ref": "#/components/schemas/sd_versions"
                          },
                          "creatorName": {
                            "$ref": "#/components/schemas/lora/properties/creatorName"
                          },
                          "description": {
                            "$ref": "#/components/schemas/lora/properties/description"
                          },
                          "name": {
                            "$ref": "#/components/schemas/lora/properties/name"
                          },
                          "urlImage": {
                            "$ref": "#/components/schemas/lora/properties/urlImage"
                          },
                          "weightDefault": {
                            "$ref": "#/components/schemas/lora/properties/weightDefault"
                          },
                          "weightMax": {
                            "$ref": "#/components/schemas/lora/properties/weightMax"
                          },
                          "weightMin": {
                            "$ref": "#/components/schemas/lora/properties/weightMin"
                          }
                        },
                        "title": "loras",
                        "type": "object"
                      },
                      "nullable": false,
                      "type": "array"
                    }
                  }
                }
              }
            },
            "description": "Responses for GET /api/rest/v1/elements."
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
      "lora": {
        "type": "object",
        "properties": {
          "akUUID": {
            "nullable": true,
            "type": "string",
            "description": "Unique identifier for the element. Elements can be found from the List Elements endpoint."
          },
          "creatorName": {
            "nullable": true,
            "type": "string",
            "description": "Name of the creator of the element"
          },
          "name": {
            "nullable": true,
            "type": "string",
            "description": "Name of the element"
          },
          "description": {
            "nullable": true,
            "type": "string",
            "description": "Description for the element"
          },
          "urlImage": {
            "nullable": true,
            "type": "string",
            "description": "URL of the element image"
          },
          "baseModel": {
            "nullable": true,
            "type": "string",
            "description": "Base model version for the element"
          },
          "weightDefault": {
            "nullable": true,
            "type": "integer",
            "description": "Default weight for the element"
          },
          "weightMin": {
            "nullable": true,
            "type": "integer",
            "description": "Minimum weight for the element"
          },
          "weightMax": {
            "nullable": true,
            "type": "integer",
            "description": "Maximum weight for the element"
          },
          "__typename": {
            "type": "string",
            "description": "Type name for introspection purposes"
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