---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Create a video generation from an image

This endpoint will generate a video using an uploaded or generated image.

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
      "name": "Motion"
    }
  ],
  "paths": {
    "/generations-image-to-video": {
      "post": {
        "tags": [
          "Motion"
        ],
        "summary": "Create a video generation from an image",
        "description": "This endpoint will generate a video using an uploaded or generated image.",
        "operationId": "createImageToVideoGeneration",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "properties": {
                  "prompt": {
                    "nullable": false,
                    "title": "String",
                    "type": "string",
                    "description": "The prompt used to generate video"
                  },
                  "imageId": {
                    "nullable": false,
                    "title": "String",
                    "type": "string",
                    "description": "The ID of the image, supports generated images and init images. Use only image or imageId with imageType."
                  },
                  "imageType": {
                    "type": "string",
                    "nullable": false,
                    "enum": [
                      "GENERATED",
                      "UPLOADED"
                    ],
                    "description": "Type indicating whether the init image is uploaded or generated. Use only image or imageId with imageType."
                  },
                  "endFrameImage": {
                    "nullable": true,
                    "title": "Object",
                    "type": "object",
                    "description": "The end frame image. Supported only on kling2_1 model when used in conjunction with an init image.",
                    "properties": {
                      "id": {
                        "nullable": false,
                        "title": "String",
                        "type": "string",
                        "description": "The ID of the end frame image."
                      },
                      "type": {
                        "nullable": false,
                        "title": "String",
                        "type": "string",
                        "enum": [
                          "GENERATED",
                          "UPLOADED"
                        ],
                        "description": "Type indicating whether the end frame image is uploaded or generated."
                      }
                    },
                    "required": [
                      "id",
                      "type"
                    ]
                  },
                  "resolution": {
                    "nullable": true,
                    "title": "String",
                    "enum": [
                      "RESOLUTION_480",
                      "RESOLUTION_720",
                      "RESOLUTION_1080"
                    ],
                    "description": "The resolution of the output video. Acceptable values vary based on model"
                  },
                  "model": {
                    "nullable": true,
                    "title": "String",
                    "enum": [
                      "MOTION2",
                      "VEO3",
                      "MOTION2FAST",
                      "VEO3FAST",
                      "KLING2_1",
                      "KLING2_5"
                    ],
                    "description": "The model to use for the video generation. Defaults to MOTION2 if not specified.",
                    "default": "MOTION2"
                  },
                  "frameInterpolation": {
                    "nullable": true,
                    "title": "Boolean",
                    "type": "boolean",
                    "description": "Smoothly blend frames for fluid video transitions using Interpolation."
                  },
                  "isPublic": {
                    "$ref": "#/components/schemas/public"
                  },
                  "seed": {
                    "type": "integer",
                    "nullable": true,
                    "title": "seed",
                    "description": "Apply a fixed seed to maintain consistency across generation sets. The maximum seed value is 2147483637 for Motion 2.0."
                  },
                  "negativePrompt": {
                    "nullable": true,
                    "title": "String",
                    "type": "string",
                    "description": "The negative prompt used for the video generation."
                  },
                  "promptEnhance": {
                    "nullable": true,
                    "title": "Boolean",
                    "type": "boolean",
                    "description": "Whether to enhance the prompt."
                  },
                  "duration": {
                    "nullable": true,
                    "title": "Integer",
                    "type": "integer",
                    "description": "Duration of the output video in seconds. Allowed values: 4, 6, or 8 on models VEO3 and VEO3FAST (default: 8) and 5 or 10 on model KLING2_5 (default: 5)."
                  },
                  "promptEnhanceInstruction": {
                    "nullable": true,
                    "title": "String",
                    "type": "string",
                    "description": "A natural language instruction used to modify the main prompt. For example, 'make it cinematic', 'add a rainbow', or 'change the subject to a cat'."
                  },
                  "styleIds": {
                    "nullable": true,
                    "title": "Array of Strings",
                    "type": "array",
                    "items": {
                      "type": "string"
                    },
                    "description": "Predefined styles to enhance the prompt. This accepts a list of style uuids."
                  },
                  "elements": {
                    "nullable": true,
                    "title": "Array of Element Inputs",
                    "type": "array",
                    "items": {
                      "$ref": "#/components/schemas/element_input"
                    },
                    "description": "An array of elements/loras objects that will be applied sequentially to the output. Elements are only supported for Motion2.0 generations. "
                  },
                  "height": {
                    "nullable": true,
                    "title": "Integer",
                    "type": "integer",
                    "description": "Height of the output video. Acceptable values vary based on model"
                  },
                  "width": {
                    "nullable": true,
                    "title": "Integer",
                    "type": "integer",
                    "description": "Width of the output video. Acceptable values vary based on model"
                  }
                },
                "type": "object",
                "required": [
                  "prompt",
                  "imageId",
                  "imageType"
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
                    "motionVideoGenerationJob": {
                      "nullable": true,
                      "properties": {
                        "generationId": {
                          "nullable": false,
                          "title": "String",
                          "type": "string"
                        },
                        "apiCreditCost": {
                          "$ref": "#/components/schemas/apiCreditCost"
                        },
                        "cost": {
                          "$ref": "#/components/schemas/cost"
                        }
                      },
                      "title": "MotionVideoGenerationOutput",
                      "type": "object"
                    }
                  }
                },
                "example": {
                  "motionVideoGenerationJob": {
                    "generationId": "i8j9k0l1-m2n3-o4p5-qrst-uv7890123456",
                    "apiCreditCost": null,
                    "cost": {
                      "amount": "0.0147",
                      "unit": "DOLLARS"
                    }
                  }
                }
              }
            },
            "description": "Responses for POST /generations-image-to-video"
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
      "public": {
        "nullable": true,
        "title": "Boolean",
        "type": "boolean",
        "description": "Whether the generation is public or not"
      },
      "element_input": {
        "nullable": false,
        "properties": {
          "akUUID": {
            "nullable": false,
            "title": "String",
            "type": "string",
            "description": "Unique identifier for element. Elements can be found from the List Elements endpoint."
          },
          "weight": {
            "nullable": true,
            "title": "Float",
            "type": "number",
            "default": 1,
            "description": "Weight for the element"
          }
        },
        "required": [
          "akUUID"
        ],
        "title": "element_input",
        "type": "object"
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