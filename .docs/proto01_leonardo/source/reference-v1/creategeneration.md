---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Create a Generation of Images

This endpoint will generate images

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
      "name": "Image"
    }
  ],
  "paths": {
    "/generations": {
      "post": {
        "tags": [
          "Image"
        ],
        "summary": "Create a Generation of Images",
        "description": "This endpoint will generate images",
        "operationId": "createGeneration",
        "requestBody": {
          "content": {
            "application/json": {
              "schema": {
                "properties": {
                  "alchemy": {
                    "nullable": true,
                    "title": "Boolean",
                    "type": "boolean",
                    "description": "Enable to use Alchemy. Note: The appropriate Alchemy version is selected for the specified model. For example, XL models will use Alchemy V2.",
                    "default": true
                  },
                  "contrastRatio": {
                    "nullable": true,
                    "title": "Float",
                    "type": "number",
                    "description": "Contrast Ratio to use with Alchemy. Must be a float between 0 and 1 inclusive."
                  },
                  "contrast": {
                    "type": "number",
                    "description": "Adjusts the contrast level of the generated image. Used in Phoenix and Flux models. Accepts values [1.0, 1.3, 1.8, 2.5, 3, 3.5, 4, 4.5]. For Phoenix, if alchemy is true, contrast needs to be 2.5 or higher.",
                    "minimum": 1,
                    "maximum": 4.5,
                    "example": 3.5,
                    "nullable": true,
                    "title": "Float"
                  },
                  "controlnets": {
                    "items": {
                      "$ref": "#/components/schemas/controlnet_input"
                    },
                    "nullable": true,
                    "type": "array"
                  },
                  "elements": {
                    "items": {
                      "$ref": "#/components/schemas/element_input"
                    },
                    "nullable": true,
                    "type": "array"
                  },
                  "userElements": {
                    "items": {
                      "$ref": "#/components/schemas/user_elements_input"
                    },
                    "nullable": true,
                    "type": "array"
                  },
                  "expandedDomain": {
                    "nullable": true,
                    "title": "Boolean",
                    "type": "boolean",
                    "description": "Enable to use the Expanded Domain feature of Alchemy."
                  },
                  "fantasyAvatar": {
                    "nullable": true,
                    "title": "Boolean",
                    "type": "boolean",
                    "description": "Enable to use the Fantasy Avatar feature."
                  },
                  "guidance_scale": {
                    "nullable": true,
                    "title": "Float",
                    "type": "number",
                    "description": "How strongly the generation should reflect the prompt. 7 is recommended. Must be between 1 and 20."
                  },
                  "height": {
                    "nullable": true,
                    "title": "Int",
                    "type": "integer",
                    "description": "The input height of the images. Must be between 32 and 1536 and be a multiple of 8. Note: Input resolution is not always the same as output resolution due to upscaling from other features.",
                    "default": 768
                  },
                  "highContrast": {
                    "nullable": true,
                    "title": "Boolean",
                    "type": "boolean",
                    "description": "Enable to use the High Contrast feature of Prompt Magic. Note: Controls RAW mode. Set to false to enable RAW mode."
                  },
                  "highResolution": {
                    "nullable": true,
                    "title": "Boolean",
                    "type": "boolean",
                    "description": "Enable to use the High Resolution feature of Prompt Magic."
                  },
                  "imagePrompts": {
                    "items": {
                      "nullable": true,
                      "title": "String",
                      "type": "string"
                    },
                    "nullable": true,
                    "type": "array"
                  },
                  "imagePromptWeight": {
                    "nullable": true,
                    "title": "Float",
                    "type": "number"
                  },
                  "init_generation_image_id": {
                    "nullable": true,
                    "title": "String",
                    "type": "string",
                    "description": "The ID of an existing image to use in image2image."
                  },
                  "init_image_id": {
                    "nullable": true,
                    "title": "String",
                    "type": "string",
                    "description": "The ID of an Init Image to use in image2image."
                  },
                  "init_strength": {
                    "nullable": true,
                    "title": "Float",
                    "type": "number",
                    "description": "How strongly the generated images should reflect the original image in image2image. Must be a float between 0.1 and 0.9."
                  },
                  "modelId": {
                    "nullable": true,
                    "title": "String",
                    "type": "string",
                    "description": "The model ID used for image generation. If not provided, uses sd_version to determine the version of Stable Diffusion to use. In-app, model IDs are under the Finetune Models menu. Click on the platform model or your custom model, then click View More. For platform models, you can also use the List Platform Models API.",
                    "default": "b24e16ff-06e3-43eb-8d33-4416c2d75876"
                  },
                  "negative_prompt": {
                    "nullable": true,
                    "title": "String",
                    "type": "string",
                    "description": "The negative prompt used for the image generation"
                  },
                  "num_images": {
                    "nullable": true,
                    "title": "Int",
                    "type": "integer",
                    "description": "The number of images to generate. Must be between 1 and 8. If either width or height is over 768, must be between 1 and 4.",
                    "default": 4
                  },
                  "num_inference_steps": {
                    "nullable": true,
                    "title": "Int",
                    "type": "integer",
                    "description": "The Step Count to use for the generation. Must be between 10 and 60. Default is 15."
                  },
                  "photoReal": {
                    "$ref": "#/components/schemas/photoRealArg"
                  },
                  "photoRealVersion": {
                    "$ref": "#/components/schemas/photoRealVersion"
                  },
                  "photoRealStrength": {
                    "$ref": "#/components/schemas/photoRealStrengthArg"
                  },
                  "presetStyle": {
                    "$ref": "#/components/schemas/sd_generation_style"
                  },
                  "prompt": {
                    "nullable": false,
                    "title": "String",
                    "type": "string",
                    "description": "The prompt used to generate images",
                    "default": "A majestic cat in the snow"
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
                  "public": {
                    "nullable": true,
                    "title": "Boolean",
                    "type": "boolean",
                    "description": "Whether the generated images should show in the community feed."
                  },
                  "scheduler": {
                    "$ref": "#/components/schemas/sd_generation_schedulers"
                  },
                  "sd_version": {
                    "$ref": "#/components/schemas/sd_versions"
                  },
                  "seed": {
                    "$ref": "#/components/schemas/seed"
                  },
                  "tiling": {
                    "nullable": true,
                    "title": "Boolean",
                    "type": "boolean",
                    "description": "Whether the generated images should tile on all axis."
                  },
                  "transparency": {
                    "nullable": true,
                    "title": "TransparencyType",
                    "type": "string",
                    "enum": [
                      "disabled",
                      "foreground_only"
                    ],
                    "description": "Which type of transparency this image should use"
                  },
                  "ultra": {
                    "nullable": true,
                    "title": "Boolean",
                    "type": "boolean",
                    "description": "Enable to use Ultra mode. Note: can not be used with Alchemy."
                  },
                  "unzoom": {
                    "nullable": true,
                    "title": "Boolean",
                    "type": "boolean",
                    "description": "Whether the generated images should be unzoomed (requires unzoomAmount and init_image_id to be set)."
                  },
                  "unzoomAmount": {
                    "nullable": true,
                    "title": "Float",
                    "type": "number",
                    "description": "How much the image should be unzoomed (requires an init_image_id and unzoom to be set to true)."
                  },
                  "upscaleRatio": {
                    "nullable": true,
                    "title": "Float",
                    "type": "number",
                    "description": "How much the image should be upscaled. (Enterprise Only)"
                  },
                  "width": {
                    "nullable": true,
                    "title": "Int",
                    "type": "integer",
                    "description": "The input width of the images. Must be between 32 and 1536 and be a multiple of 8. Note: Input resolution is not always the same as output resolution due to upscaling from other features.",
                    "default": 1024
                  },
                  "controlNet": {
                    "nullable": true,
                    "title": "Boolean",
                    "type": "boolean",
                    "description": "This parameter will be deprecated in September 2024. Please use the controlnets array instead.",
                    "deprecated": true
                  },
                  "controlNetType": {
                    "$ref": "#/components/schemas/controlnet_type",
                    "deprecated": true
                  },
                  "weighting": {
                    "nullable": true,
                    "title": "Float",
                    "type": "number",
                    "description": "This parameter will be deprecated in September 2024. Please use the controlnets array instead.",
                    "deprecated": true
                  },
                  "canvasRequest": {
                    "nullable": true,
                    "title": "Boolean",
                    "type": "boolean",
                    "description": "Whether the generation is for the Canvas Editor feature."
                  },
                  "canvasRequestType": {
                    "$ref": "#/components/schemas/canvasRequestType"
                  },
                  "canvasInitId": {
                    "nullable": true,
                    "title": "String",
                    "type": "string",
                    "description": "The ID of an initial image to use in Canvas Editor request."
                  },
                  "canvasMaskId": {
                    "nullable": true,
                    "title": "String",
                    "type": "string",
                    "description": "The ID of a mask image to use in Canvas Editor request."
                  },
                  "enhancePrompt": {
                    "nullable": true,
                    "title": "Boolean",
                    "type": "boolean",
                    "description": "When enabled, your prompt is expanded to include more detail."
                  },
                  "enhancePromptInstruction": {
                    "nullable": true,
                    "title": "String",
                    "type": "string",
                    "description": "When enhancePrompt is enabled, the prompt is enhanced based on the given instructions."
                  }
                },
                "type": "object",
                "required": [
                  "prompt"
                ]
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
                    "sdGenerationJob": {
                      "nullable": true,
                      "properties": {
                        "generationId": {
                          "nullable": false,
                          "title": "String",
                          "type": "string"
                        },
                        "apiCreditCost": {
                          "nullable": true,
                          "type": "integer",
                          "description": "API Credits Cost for Image Generation. Available for Production API Users. Note: it will be deprecated. Please use the cost instead.",
                          "deprecated": true
                        },
                        "cost": {
                          "$ref": "#/components/schemas/cost"
                        }
                      },
                      "title": "SDGenerationOutput",
                      "type": "object"
                    }
                  }
                },
                "example": {
                  "sdGenerationJob": {
                    "generationId": "a1b2c3d4-e5f6-7890-abcd-ef1234567890",
                    "apiCreditCost": null,
                    "cost": {
                      "amount": "0.0147",
                      "unit": "DOLLARS"
                    }
                  }
                }
              }
            },
            "description": "Responses for POST /generations"
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
      "sd_generation_schedulers": {
        "type": "string",
        "nullable": false,
        "title": "sd_generation_schedulers",
        "enum": [
          "KLMS",
          "EULER_ANCESTRAL_DISCRETE",
          "EULER_DISCRETE",
          "DDIM",
          "DPM_SOLVER",
          "PNDM",
          "LEONARDO"
        ],
        "description": "The scheduler to generate images with. Defaults to EULER_DISCRETE if not specified."
      },
      "controlnet_input": {
        "nullable": false,
        "properties": {
          "initImageId": {
            "nullable": false,
            "title": "String",
            "type": "string",
            "description": "The ID of the init image"
          },
          "initImageType": {
            "type": "string",
            "nullable": false,
            "enum": [
              "GENERATED",
              "UPLOADED"
            ],
            "description": "Type indicating whether the init image is uploaded or generated."
          },
          "preprocessorId": {
            "nullable": false,
            "title": "numeric",
            "type": "number",
            "description": "ID of the controlnet. A list of compatible IDs can be found in our guides."
          },
          "weight": {
            "nullable": true,
            "title": "Float",
            "type": "number",
            "description": "Weight for the controlnet"
          },
          "strengthType": {
            "type": "string",
            "nullable": true,
            "enum": [
              "Low",
              "Mid",
              "High",
              "Ultra",
              "Max"
            ],
            "description": "Strength type for the controlnet. Can only be used for Style, Character and Content Reference controlnets."
          }
        },
        "title": "controlnet_input",
        "type": "object"
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
      },
      "user_elements_input": {
        "nullable": false,
        "properties": {
          "userLoraId": {
            "nullable": true,
            "title": "Int",
            "type": "number",
            "description": "Unique identifier for user custom element."
          },
          "weight": {
            "nullable": true,
            "title": "Float",
            "type": "number",
            "description": "Weight for the element"
          }
        },
        "title": "user_elements_input",
        "type": "object"
      },
      "seed": {
        "type": "integer",
        "nullable": true,
        "title": "seed",
        "description": "Apply a fixed seed to maintain consistency across generation sets. The maximum seed value is 2147483637 for Flux and 9999999998 for other models"
      },
      "sd_generation_style": {
        "type": "string",
        "nullable": true,
        "title": "sd_generation_style",
        "enum": [
          "ANIME",
          "BOKEH",
          "CINEMATIC",
          "CINEMATIC_CLOSEUP",
          "CREATIVE",
          "DYNAMIC",
          "ENVIRONMENT",
          "FASHION",
          "FILM",
          "FOOD",
          "GENERAL",
          "HDR",
          "ILLUSTRATION",
          "LEONARDO",
          "LONG_EXPOSURE",
          "MACRO",
          "MINIMALISTIC",
          "MONOCHROME",
          "MOODY",
          "NONE",
          "NEUTRAL",
          "PHOTOGRAPHY",
          "PORTRAIT",
          "RAYTRACED",
          "RENDER_3D",
          "RETRO",
          "SKETCH_BW",
          "SKETCH_COLOR",
          "STOCK_PHOTO",
          "VIBRANT",
          "UNPROCESSED"
        ],
        "description": "The style to generate images with. When photoReal is enabled, refer to the Guide section for a full list. When alchemy is disabled, use LEONARDO or NONE. When alchemy is enabled, use ANIME, CREATIVE, DYNAMIC, ENVIRONMENT, GENERAL, ILLUSTRATION, PHOTOGRAPHY, RAYTRACED, RENDER_3D, SKETCH_BW, SKETCH_COLOR, or NONE.",
        "default": "DYNAMIC"
      },
      "controlnet_type": {
        "type": "string",
        "nullable": false,
        "title": "controlnet_type",
        "enum": [
          "POSE",
          "CANNY",
          "DEPTH"
        ],
        "description": "This parameter will be deprecated in September 2024. Please use the controlnets array instead.",
        "deprecated": true
      },
      "photoRealArg": {
        "nullable": true,
        "title": "Boolean",
        "type": "boolean",
        "description": "Enable the photoReal feature. Requires enabling alchemy and unspecifying modelId (for photoRealVersion V1)."
      },
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
      "canvasRequestType": {
        "type": "string",
        "nullable": true,
        "title": "canvasRequestType",
        "enum": [
          "INPAINT",
          "OUTPAINT",
          "SKETCH2IMG",
          "IMG2IMG"
        ],
        "description": "The type of request for the Canvas Editor."
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