---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Perform instant refine on a LCM image

This endpoint will perform instant refine on a LCM image

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
      "name": "Realtime Canvas"
    }
  ],
  "paths": {
    "/lcm-instant-refine": {
      "post": {
        "tags": [
          "Realtime Canvas"
        ],
        "summary": "Perform instant refine on a LCM image",
        "description": "This endpoint will perform instant refine on a LCM image",
        "operationId": "performInstantRefine",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "properties": {
                  "imageDataUrl": {
                    "nullable": false,
                    "title": "String",
                    "type": "string",
                    "description": "Image data used to generate image. In base64 format. Prefix: `data:image/jpeg;base64,`"
                  },
                  "prompt": {
                    "nullable": false,
                    "title": "String",
                    "type": "string",
                    "description": "The prompt used to generate images"
                  },
                  "guidance": {
                    "nullable": true,
                    "title": "Float",
                    "type": "number",
                    "description": "How strongly the generation should reflect the prompt. Must be a float between 0.5 and 20."
                  },
                  "strength": {
                    "nullable": true,
                    "title": "Float",
                    "type": "number",
                    "description": "Creativity strength of generation. Higher strength will deviate more from the original image supplied in imageDataUrl. Must be a float between 0.1 and 1."
                  },
                  "requestTimestamp": {
                    "$ref": "#/components/schemas/timestamp"
                  },
                  "style": {
                    "$ref": "#/components/schemas/lcm_generation_style"
                  },
                  "steps": {
                    "nullable": true,
                    "title": "Int",
                    "type": "integer",
                    "description": "The number of steps to use for the generation. Must be between 4 and 16."
                  },
                  "width": {
                    "nullable": true,
                    "title": "Int",
                    "type": "integer",
                    "description": "The output width of the image. Must be 512, 640 or 1024.",
                    "default": 512
                  },
                  "height": {
                    "nullable": true,
                    "title": "Int",
                    "type": "integer",
                    "description": "The output width of the image. Must be 512, 640 or 1024.",
                    "default": 512
                  },
                  "seed": {
                    "$ref": "#/components/schemas/seed"
                  }
                },
                "type": "object",
                "required": [
                  "imageDataUrl",
                  "prompt"
                ]
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
                  "type": "object",
                  "properties": {
                    "lcmGenerationJob": {
                      "nullable": true,
                      "properties": {
                        "imageDataUrl": {
                          "nullable": false,
                          "title": "Array of Strings",
                          "type": "array",
                          "items": {
                            "type": "string"
                          }
                        },
                        "requestTimestamp": {
                          "$ref": "#/components/schemas/timestamp"
                        },
                        "apiCreditCost": {
                          "$ref": "#/components/schemas/apiCreditCost"
                        },
                        "cost": {
                          "$ref": "#/components/schemas/cost"
                        }
                      },
                      "title": "LcmGenerationOutput",
                      "type": "object"
                    }
                  }
                },
                "example": {
                  "lcmGenerationJob": {
                    "imageDataUrl": [
                      "data:image/jpeg;base64,/9j/4AAQSkZJRgABAQEAAAAAAAD..."
                    ],
                    "requestTimestamp": "1234567891",
                    "apiCreditCost": null,
                    "cost": {
                      "amount": "0.0147",
                      "unit": "DOLLARS"
                    }
                  }
                }
              }
            },
            "description": "Responses for POST /lcm-instant-refine"
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
      "apiCreditCost": {
        "nullable": true,
        "title": "Int",
        "type": "integer",
        "description": "API credits cost, available for Production API users. Note: it will be deprecated. Please use the cost instead.",
        "deprecated": true
      },
      "timestamp": {
        "type": "string",
        "nullable": false,
        "title": "timestamp"
      },
      "seed": {
        "type": "integer",
        "nullable": true,
        "title": "seed",
        "description": "Apply a fixed seed to maintain consistency across generation sets. The maximum seed value is 2147483637 for Flux and 9999999998 for other models"
      },
      "lcm_generation_style": {
        "type": "string",
        "nullable": true,
        "title": "lcm_generation_style",
        "enum": [
          "ANIME",
          "CINEMATIC",
          "DIGITAL_ART",
          "DYNAMIC",
          "ENVIRONMENT",
          "FANTASY_ART",
          "ILLUSTRATION",
          "PHOTOGRAPHY",
          "RENDER_3D",
          "RAYTRACED",
          "SKETCH_BW",
          "SKETCH_COLOR",
          "VIBRANT",
          "NONE"
        ],
        "description": "The style to generate LCM images with."
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