---
updatedAt: 2026-06-03T21:44:56.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Calculating API Cost

This endpoint returns the cost used for generating images using a particular service type.

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
      "name": "Pricing Calculator"
    }
  ],
  "paths": {
    "/pricing-calculator": {
      "post": {
        "tags": [
          "Pricing Calculator"
        ],
        "summary": "Calculating API Cost",
        "description": "This endpoint returns the cost used for generating images using a particular service type.",
        "operationId": "pricingCalculator",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "type": "object",
                "properties": {
                  "service": {
                    "$ref": "#/components/schemas/pricingCalculatorServices"
                  },
                  "serviceParams": {
                    "nullable": false,
                    "title": "Object",
                    "type": "object",
                    "description": "Parameters for the service",
                    "properties": {
                      "IMAGE_GENERATION": {
                        "nullable": true,
                        "title": "Object",
                        "type": "object",
                        "description": "Parameters for IMAGE_GENERATION service",
                        "properties": {
                          "imageHeight": {
                            "$ref": "#/components/schemas/imageHeight"
                          },
                          "imageWidth": {
                            "$ref": "#/components/schemas/imageHeight"
                          },
                          "numImages": {
                            "$ref": "#/components/schemas/numImages"
                          },
                          "inferenceSteps": {
                            "nullable": false,
                            "title": "Int",
                            "type": "integer",
                            "description": "The Step Count to use for the generation. Must be between 10 and 60."
                          },
                          "promptMagic": {
                            "$ref": "#/components/schemas/promptMagicArg"
                          },
                          "promptMagicStrength": {
                            "$ref": "#/components/schemas/promptMagicStrengthArg"
                          },
                          "promptMagicVersion": {
                            "$ref": "#/components/schemas/promptMagicVersionArg"
                          },
                          "alchemyMode": {
                            "nullable": false,
                            "title": "Boolean",
                            "type": "boolean",
                            "description": "Enable to use Alchemy."
                          },
                          "photoRealMode": {
                            "nullable": true,
                            "title": "Boolean",
                            "type": "boolean",
                            "description": "Enable to use PhotoReal. Requires enabling alchemy."
                          },
                          "photoRealStrength": {
                            "$ref": "#/components/schemas/photoRealStrengthArg"
                          },
                          "photoRealVersion": {
                            "$ref": "#/components/schemas/photoRealVersion"
                          },
                          "highResolution": {
                            "nullable": false,
                            "title": "Boolean",
                            "type": "boolean",
                            "description": "Enable to use high resolution."
                          },
                          "loraCount": {
                            "nullable": true,
                            "title": "Int",
                            "type": "integer",
                            "description": "The number of elements used for the generation."
                          },
                          "isModelCustom": {
                            "nullable": true,
                            "title": "Boolean",
                            "type": "boolean",
                            "description": "Enable to use custom model."
                          },
                          "controlnetsCost": {
                            "nullable": true,
                            "title": "Int",
                            "type": "integer",
                            "description": "The total cost of controlnets input."
                          },
                          "isPhoenix": {
                            "nullable": true,
                            "title": "Boolean",
                            "type": "boolean",
                            "description": "Enable to use Phoenix model."
                          },
                          "isSDXL": {
                            "nullable": true,
                            "title": "Boolean",
                            "type": "boolean",
                            "description": "Enable to use SDXL model."
                          },
                          "isSDXLLightning": {
                            "nullable": true,
                            "title": "Boolean",
                            "type": "boolean",
                            "description": "Enable to use SDXL Lightning model."
                          },
                          "isUltra": {
                            "nullable": true,
                            "title": "Boolean",
                            "type": "boolean",
                            "description": "Enable to use Ultra mode."
                          },
                          "isFluxSchnell": {
                            "nullable": true,
                            "title": "Boolean",
                            "type": "boolean",
                            "description": "Enable to use Flux Schnell model."
                          },
                          "isFluxDev": {
                            "nullable": true,
                            "title": "Boolean",
                            "type": "boolean",
                            "description": "Enable to use Flux Dev model."
                          },
                          "isFluxKontext": {
                            "nullable": true,
                            "title": "Boolean",
                            "type": "boolean",
                            "description": "Enable to use Flux Kontext model."
                          }
                        }
                      },
                      "FANTASY_AVATAR_GENERATION": {
                        "nullable": true,
                        "title": "Object",
                        "type": "object",
                        "description": "Parameters for FANTASY_AVATAR_GENERATION service",
                        "properties": {
                          "imageHeight": {
                            "$ref": "#/components/schemas/imageHeight"
                          },
                          "imageWidth": {
                            "$ref": "#/components/schemas/imageHeight"
                          },
                          "numImages": {
                            "$ref": "#/components/schemas/numImages"
                          }
                        }
                      },
                      "MOTION_SVD_GENERATION": {
                        "nullable": true,
                        "title": "Object",
                        "type": "object",
                        "description": "Parameters for MOTION_SVD_GENERATION service",
                        "properties": {}
                      },
                      "MOTION_VIDEO_GENERATION": {
                        "nullable": true,
                        "title": "Object",
                        "type": "object",
                        "description": "Parameters for MOTION_VIDEO_GENERATION service",
                        "properties": {
                          "resolution": {
                            "nullable": false,
                            "title": "String",
                            "type": "string",
                            "description": "The resolution of the video. Must be RESOLUTION_480 or RESOLUTION_720."
                          }
                        }
                      },
                      "VEO3_MOTION_VIDEO_GENERATION": {
                        "nullable": true,
                        "title": "Object",
                        "type": "object",
                        "description": "Parameters for VEO3_MOTION_VIDEO_GENERATION service",
                        "properties": {
                          "resolution": {
                            "nullable": false,
                            "title": "String",
                            "type": "string",
                            "enum": [
                              "RESOLUTION_720"
                            ],
                            "description": "The resolution of the video. Supported resolution for VEO3 is RESOLUTION_720."
                          }
                        }
                      },
                      "LCM_GENERATION": {
                        "nullable": true,
                        "title": "Object",
                        "type": "object",
                        "description": "Parameters for LCM_GENERATION service",
                        "properties": {
                          "height": {
                            "nullable": true,
                            "title": "Int",
                            "type": "integer",
                            "description": "The output height of the image. Must be 512, 640 or 1024."
                          },
                          "width": {
                            "nullable": true,
                            "title": "Int",
                            "type": "integer",
                            "description": "The output width of the image. Must be 512, 640 or 1024."
                          },
                          "instantRefine": {
                            "nullable": true,
                            "title": "Boolean",
                            "type": "boolean",
                            "description": "Enable for instant upscale"
                          },
                          "refine": {
                            "nullable": true,
                            "title": "Boolean",
                            "type": "boolean",
                            "description": "Enable for normal alchemy upscale"
                          }
                        }
                      },
                      "MODEL_TRAINING": {
                        "nullable": true,
                        "title": "Object",
                        "type": "object",
                        "description": "Parameters for MODEL_TRAINING service",
                        "properties": {
                          "resolution": {
                            "nullable": false,
                            "title": "Int",
                            "type": "integer",
                            "description": "The resolution for training. Must be 512, 768, or 1024."
                          },
                          "sd_version": {
                            "nullable": true,
                            "title": "sd_version",
                            "enum": [
                              "FLUX_DEV"
                            ],
                            "description": "The model for the training. Can be set to 'FLUX_DEV' for FLUX_DEV specific pricing or can be omitted."
                          },
                          "datasetImageCount": {
                            "nullable": true,
                            "title": "Int",
                            "type": "integer",
                            "description": "The number of images in the training dataset when sd_version is set to 'FLUX_DEV'. Must be between 1 and 50."
                          }
                        }
                      },
                      "TEXTURE_GENERATION": {
                        "nullable": true,
                        "title": "Object",
                        "type": "object",
                        "description": "Parameters for TEXTURE_GENERATION service",
                        "properties": {
                          "preview": {
                            "nullable": false,
                            "title": "Boolean",
                            "type": "boolean"
                          }
                        }
                      },
                      "UNIVERSAL_UPSCALER": {
                        "nullable": true,
                        "title": "Object",
                        "type": "object",
                        "description": "Parameters for UNIVERSAL_UPSCALER service",
                        "properties": {
                          "megapixel": {
                            "nullable": false,
                            "title": "Int",
                            "type": "integer",
                            "description": "The maximum upscaled image size is 20 megapixels."
                          }
                        }
                      },
                      "UNIVERSAL_UPSCALER_ULTRA": {
                        "nullable": true,
                        "title": "Object",
                        "type": "object",
                        "description": "Parameters for UNIVERSAL_UPSCALER_ULTRA service",
                        "properties": {
                          "inputWidth": {
                            "nullable": false,
                            "title": "Int",
                            "type": "integer",
                            "description": "The input width of the image."
                          },
                          "inputHeight": {
                            "nullable": false,
                            "title": "Int",
                            "type": "integer",
                            "description": "The input height of the image."
                          },
                          "upscaleMultiplier": {
                            "nullable": false,
                            "title": "Float",
                            "type": "number",
                            "description": "The upscale multiplier of the universal upscaler. Must be between 1.00 and 2.00."
                          }
                        }
                      }
                    }
                  }
                }
              }
            }
          }
        },
        "responses": {
          "200": {
            "content": {
              "application/json": {
                "schema": {
                  "type": "object",
                  "properties": {
                    "calculateProductionApiServiceCost": {
                      "nullable": true,
                      "properties": {
                        "cost": {
                          "nullable": false,
                          "title": "Int",
                          "type": "integer",
                          "description": "API service cost to generate the image."
                        }
                      },
                      "title": "calculateProductionApiServiceCost",
                      "type": "object"
                    }
                  }
                }
              }
            },
            "description": "Responses for POST /pricing-calculator"
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "photoRealVersion": {
        "nullable": true,
        "title": "String",
        "type": "string",
        "description": "The version of photoReal to use. Must be v1 or v2."
      },
      "photoRealStrengthArg": {
        "nullable": true,
        "title": "Float",
        "type": "number",
        "description": "Depth of field of photoReal. Must be 0.55 for low, 0.5 for medium, or 0.45 for high. Defaults to 0.55 if not specified."
      },
      "promptMagicArg": {
        "nullable": true,
        "title": "Boolean",
        "type": "boolean",
        "description": "Enable to use Prompt Magic."
      },
      "promptMagicVersionArg": {
        "nullable": true,
        "title": "String",
        "type": "string",
        "description": "Prompt magic version v2 or v3, for use when promptMagic: true"
      },
      "promptMagicStrengthArg": {
        "nullable": true,
        "title": "Float",
        "type": "number",
        "description": "Strength of prompt magic. Must be a float between 0.1 and 1.0"
      },
      "pricingCalculatorServices": {
        "type": "string",
        "nullable": false,
        "title": "pricingCalculatorServices",
        "enum": [
          "IMAGE_GENERATION",
          "FANTASY_AVATAR_GENERATION",
          "MOTION_SVD_GENERATION",
          "MOTION_VIDEO_GENERATION",
          "VEO3_MOTION_VIDEO_GENERATION",
          "LCM_GENERATION",
          "MODEL_TRAINING",
          "TEXTURE_GENERATION",
          "UNIVERSAL_UPSCALER",
          "UNIVERSAL_UPSCALER_ULTRA"
        ],
        "description": "The services to be chosen for calculating the API credit cost."
      },
      "imageHeight": {
        "nullable": false,
        "title": "Int",
        "type": "integer",
        "description": "The input height of the images. Must be between 32 and 1024 and be a multiple of 8. Note: Input resolution is not always the same as output resolution due to upscaling from other features"
      },
      "numImages": {
        "nullable": false,
        "title": "Int",
        "type": "integer",
        "description": "The number of images to generate. Must be between 1 and 8. If either width or height is over 768, must be between 1 and 4."
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