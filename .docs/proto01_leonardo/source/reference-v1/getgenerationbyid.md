---
updatedAt: 2026-06-03T01:26:05.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Get a Single Generation

This endpoint will provide information about a specific generation

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
    "/generations/{id}": {
      "get": {
        "tags": [
          "Image"
        ],
        "summary": "Get a Single Generation",
        "description": "This endpoint will provide information about a specific generation",
        "operationId": "getGenerationById",
        "parameters": [
          {
            "required": true,
            "description": "The ID of the generation to return.",
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
                    "generations_by_pk": {
                      "description": "columns and relationships of \"generations\"",
                      "nullable": true,
                      "properties": {
                        "createdAt": {
                          "$ref": "#/components/schemas/timestamp"
                        },
                        "generated_images": {
                          "items": {
                            "description": "columns and relationships of \"generated_images\"",
                            "nullable": false,
                            "properties": {
                              "generated_image_variation_generics": {
                                "items": {
                                  "description": "columns and relationships of \"generated_image_variation_generic\"",
                                  "nullable": false,
                                  "properties": {
                                    "id": {
                                      "$ref": "#/components/schemas/uuid"
                                    },
                                    "status": {
                                      "$ref": "#/components/schemas/job_status"
                                    },
                                    "transformType": {
                                      "$ref": "#/components/schemas/VARIATION_TYPE"
                                    },
                                    "url": {
                                      "nullable": true,
                                      "title": "String",
                                      "type": "string"
                                    }
                                  },
                                  "title": "generated_image_variation_generic",
                                  "type": "object"
                                },
                                "nullable": false,
                                "type": "array"
                              },
                              "fantasyAvatar": {
                                "nullable": true,
                                "title": "Boolean",
                                "type": "boolean",
                                "description": "If fantasyAvatar feature was used."
                              },
                              "id": {
                                "$ref": "#/components/schemas/uuid"
                              },
                              "imageToVideo": {
                                "$ref": "#/components/schemas/imageToVideo"
                              },
                              "likeCount": {
                                "nullable": false,
                                "title": "Int",
                                "type": "integer"
                              },
                              "motion": {
                                "$ref": "#/components/schemas/motion"
                              },
                              "motionModel": {
                                "$ref": "#/components/schemas/motionModel"
                              },
                              "motionMP4URL": {
                                "$ref": "#/components/schemas/motionMP4URL"
                              },
                              "motionStrength": {
                                "$ref": "#/components/schemas/motionStrength"
                              },
                              "nsfw": {
                                "nullable": false,
                                "title": "Boolean",
                                "type": "boolean"
                              },
                              "url": {
                                "nullable": false,
                                "title": "String",
                                "type": "string"
                              }
                            },
                            "title": "generated_images",
                            "type": "object"
                          },
                          "nullable": false,
                          "type": "array"
                        },
                        "generation_elements": {
                          "items": {
                            "description": "This table captures the elements that are applied to Generations.",
                            "nullable": false,
                            "properties": {
                              "id": {
                                "$ref": "#/components/schemas/bigint"
                              },
                              "lora": {
                                "description": "Element used for the generation.",
                                "nullable": true,
                                "properties": {
                                  "akUUID": {
                                    "$ref": "#/components/schemas/lora/properties/akUUID"
                                  },
                                  "baseModel": {
                                    "$ref": "#/components/schemas/sd_versions"
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
                              "weightApplied": {
                                "$ref": "#/components/schemas/numeric"
                              }
                            },
                            "title": "generation_elements",
                            "type": "object"
                          },
                          "nullable": false,
                          "type": "array"
                        },
                        "guidanceScale": {
                          "$ref": "#/components/schemas/float8"
                        },
                        "id": {
                          "$ref": "#/components/schemas/uuid"
                        },
                        "imageHeight": {
                          "nullable": false,
                          "title": "Int",
                          "type": "integer"
                        },
                        "imageWidth": {
                          "nullable": false,
                          "title": "Int",
                          "type": "integer"
                        },
                        "inferenceSteps": {
                          "nullable": true,
                          "title": "Int",
                          "type": "integer"
                        },
                        "initStrength": {
                          "$ref": "#/components/schemas/float8"
                        },
                        "modelId": {
                          "$ref": "#/components/schemas/uuid"
                        },
                        "negativePrompt": {
                          "nullable": true,
                          "title": "String",
                          "type": "string"
                        },
                        "photoReal": {
                          "$ref": "#/components/schemas/photoRealRes"
                        },
                        "photoRealStrength": {
                          "$ref": "#/components/schemas/photoRealStrengthRes"
                        },
                        "presetStyle": {
                          "$ref": "#/components/schemas/sd_generation_style"
                        },
                        "prompt": {
                          "nullable": false,
                          "title": "String",
                          "type": "string"
                        },
                        "promptMagic": {
                          "$ref": "#/components/schemas/promptMagicRes"
                        },
                        "promptMagicStrength": {
                          "$ref": "#/components/schemas/promptMagicStrengthRes"
                        },
                        "promptMagicVersion": {
                          "$ref": "#/components/schemas/promptMagicVersionRes"
                        },
                        "public": {
                          "nullable": false,
                          "title": "Boolean",
                          "type": "boolean"
                        },
                        "scheduler": {
                          "$ref": "#/components/schemas/sd_generation_schedulers"
                        },
                        "sdVersion": {
                          "$ref": "#/components/schemas/sd_versions"
                        },
                        "seed": {
                          "$ref": "#/components/schemas/seed"
                        },
                        "status": {
                          "$ref": "#/components/schemas/job_status"
                        },
                        "ultra": {
                          "$ref": "#/components/schemas/sd_generation_ultra"
                        }
                      },
                      "title": "generations",
                      "type": "object"
                    }
                  }
                }
              }
            },
            "description": "Responses for GET /generations/{id}"
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "imageToVideo": {
        "nullable": true,
        "title": "Boolean",
        "type": "boolean",
        "description": "If it is an image to video generation."
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
      },
      "motion": {
        "nullable": true,
        "title": "Boolean",
        "type": "boolean",
        "description": "If generation is of motion type."
      },
      "motionModel": {
        "nullable": true,
        "title": "String",
        "type": "string",
        "description": "The name of the motion model."
      },
      "motionMP4URL": {
        "nullable": true,
        "title": "String",
        "type": "string",
        "description": "The URL of the motion MP4."
      },
      "motionStrength": {
        "nullable": true,
        "title": "Int",
        "type": "integer",
        "description": "The motion strength."
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
      "VARIATION_TYPE": {
        "type": "string",
        "nullable": false,
        "title": "VARIATION_TYPE",
        "enum": [
          "OUTPAINT",
          "INPAINT",
          "UPSCALE",
          "UNZOOM",
          "NOBG"
        ],
        "description": "The type of variation."
      },
      "timestamp": {
        "type": "string",
        "nullable": false,
        "title": "timestamp"
      },
      "float8": {
        "type": "number",
        "nullable": true,
        "title": "float8"
      },
      "numeric": {
        "type": "number",
        "nullable": true,
        "title": "numeric"
      },
      "bigint": {
        "type": "integer",
        "nullable": true,
        "title": "bigint"
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
      "uuid": {
        "nullable": true,
        "pattern": "[a-f0-9]{8}-[a-f0-9]{4}-4[a-f0-9]{3}-[89aAbB][a-f0-9]{3}-[a-f0-9]{12}",
        "title": "uuid",
        "type": "string"
      },
      "photoRealRes": {
        "nullable": true,
        "title": "Boolean",
        "type": "boolean",
        "description": "If photoReal feature was used."
      },
      "photoRealStrengthRes": {
        "nullable": true,
        "title": "Float",
        "type": "number",
        "description": "Depth of field of photoReal used. 0.55 is low, 0.5 is medium, and 0.45 is high. Default is 0.55."
      },
      "promptMagicRes": {
        "nullable": true,
        "title": "Boolean",
        "type": "boolean",
        "description": "If prompt magic was used."
      },
      "promptMagicVersionRes": {
        "nullable": true,
        "title": "String",
        "type": "string",
        "description": "Version of prompt magic used."
      },
      "promptMagicStrengthRes": {
        "nullable": true,
        "title": "Float",
        "type": "number",
        "description": "Strength of prompt magic used."
      },
      "sd_generation_ultra": {
        "nullable": true,
        "title": "Boolean",
        "type": "boolean",
        "description": "If ultra generation mode was used."
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