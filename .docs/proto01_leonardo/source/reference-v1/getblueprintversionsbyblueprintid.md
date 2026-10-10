---
updatedAt: 2026-04-21T23:42:41.000Z
agentTools:
  projectIndex: https://docs.leonardo.ai/v1.0/llms.txt
---

# Get Blueprint Versions by Blueprint ID

Returns all versions of a Blueprint by its akUUID

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
      "name": "Blueprints"
    }
  ],
  "paths": {
    "/blueprints/{id}/versions": {
      "get": {
        "tags": [
          "Blueprints"
        ],
        "summary": "Get Blueprint Versions by Blueprint ID",
        "description": "Returns all versions of a Blueprint by its akUUID",
        "operationId": "getBlueprintVersionsByBlueprintId",
        "parameters": [
          {
            "name": "id",
            "in": "path",
            "required": true,
            "description": "The akUUID of the Blueprint",
            "schema": {
              "type": "string",
              "format": "uuid"
            }
          }
        ],
        "responses": {
          "200": {
            "description": "Successfully retrieved Blueprint Versions",
            "content": {
              "application/json": {
                "schema": {
                  "oneOf": [
                    {
                      "type": "object",
                      "title": "Success Response",
                      "properties": {
                        "blueprintVersions": {
                          "$ref": "#/components/schemas/BlueprintVersion"
                        }
                      }
                    },
                    {
                      "type": "array",
                      "title": "Error Response",
                      "description": "Error response (validation, not found, etc.)",
                      "items": {
                        "$ref": "#/components/schemas/ApiError"
                      }
                    }
                  ]
                },
                "examples": {
                  "success": {
                    "summary": "Successful response",
                    "value": {
                      "blueprintVersions": {
                        "edges": [
                          {
                            "cursor": "eyJjcmVhdGVkQXQiOiIyMDI1LTExLTI3VDA1OjEzOjIxLjg5NloiLCJha1VVSUQiOiI5NTZlOTU2NC0xOWY3LTQ5NjgtYjU2ZC0wNWMyYzU2NzcyNmYifQ==",
                            "node": {
                              "akUUID": "956e9564-19f7-4968-b56d-05c2c567726f",
                              "createdAt": "2025-11-27T05:13:21.896Z",
                              "updatedAt": "2025-11-27T05:13:21.896Z",
                              "cost": 160,
                              "uiMetadata": {
                                "inputs": [
                                  {
                                    "type": "image",
                                    "label": "Upload a Photo of Yourself",
                                    "nodeId": "4a5d62d9-5d73-4a2f-92ee-3a67d37b2b58",
                                    "required": true,
                                    "placeholder": "Upload a selfie or photo of a person, preferrably from the chest up. Works better with clear front facing photos",
                                    "settingName": "imageUrl"
                                  }
                                ],
                                "outputs": [
                                  {
                                    "type": "image"
                                  },
                                  {
                                    "type": "image"
                                  },
                                  {
                                    "type": "image"
                                  },
                                  {
                                    "type": "image"
                                  }
                                ]
                              },
                              "uiMetadataSchemaVersion": "21",
                              "models": [
                                "gemini-2.5-flash-image"
                              ],
                              "executability": {
                                "isExecutable": true,
                                "reasons": [
                                  {
                                    "models": "gemini-2.5-flash-image"
                                  }
                                ]
                              }
                            }
                          }
                        ],
                        "totalCount": 1,
                        "pageInfo": {
                          "hasNextPage": false,
                          "hasPreviousPage": false,
                          "startCursor": "eyJjcmVhdGVkQXQiOiIyMDI1LTExLTI3VDA1OjEzOjIxLjg5NloiLCJha1VVSUQiOiI5NTZlOTU2NC0xOWY3LTQ5NjgtYjU2ZC0wNWMyYzU2NzcyNmYifQ==",
                          "endCursor": "eyJjcmVhdGVkQXQiOiIyMDI1LTEwLTMwVDA0OjU5OjAyLjEwOVoiLCJha1VVSUQiOiI4NzNlN2FlZS0wZTIzLTQ2NTEtYTllMi0zZTkwZGY3ZGYyNTkifQ=="
                        }
                      }
                    }
                  },
                  "badRequest": {
                    "summary": "Bad request error",
                    "value": [
                      {
                        "message": "An error occurred.",
                        "path": [
                          "blueprintVersions"
                        ],
                        "locations": [
                          {
                            "column": 20,
                            "line": 1
                          }
                        ],
                        "extensions": {
                          "code": "BadRequestException",
                          "details": {
                            "message": "Bad request. Please check your input.",
                            "statusCode": 400
                          }
                        }
                      }
                    ]
                  },
                  "notFound": {
                    "summary": "Not found error",
                    "value": [
                      {
                        "message": "Blueprint not found",
                        "path": [
                          "blueprintVersions"
                        ],
                        "locations": [
                          {
                            "column": 20,
                            "line": 1
                          }
                        ],
                        "extensions": {
                          "code": "NOT_FOUND",
                          "errorCode": 0,
                          "statusCode": 404
                        }
                      }
                    ]
                  }
                }
              }
            }
          }
        }
      }
    }
  },
  "components": {
    "schemas": {
      "BlueprintVersion": {
        "type": "object",
        "title": "BlueprintVersion",
        "description": "A Blueprint Version object",
        "properties": {
          "edges": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "cursor": {
                  "type": "string",
                  "example": "eyJjcmVhdGVkQXQiOiIyMDI1LTExLTI3VDA1OjEzOjIxLjg5NloiLCJha1VVSUQiOiI5NTZlOTU2NC0xOWY3LTQ5NjgtYjU2ZC0wNWMyYzU2NzcyNmYifQ=="
                },
                "node": {
                  "type": "object",
                  "properties": {
                    "akUUID": {
                      "type": "string",
                      "format": "uuid",
                      "example": "956e9564-19f7-4968-b56d-05c2c567726f"
                    },
                    "createdAt": {
                      "type": "string",
                      "format": "date-time",
                      "example": "2025-11-27T05:13:21.896Z"
                    },
                    "updatedAt": {
                      "type": "string",
                      "format": "date-time",
                      "example": "2025-11-27T05:13:21.896Z"
                    },
                    "cost": {
                      "type": "integer",
                      "example": 160
                    },
                    "uiMetadata": {
                      "type": "object",
                      "properties": {
                        "inputs": {
                          "type": "array",
                          "items": {
                            "type": "object"
                          }
                        },
                        "outputs": {
                          "type": "array",
                          "items": {
                            "type": "object"
                          }
                        }
                      },
                      "additionalProperties": false
                    },
                    "uiMetadataSchemaVersion": {
                      "type": "string",
                      "example": "21"
                    },
                    "models": {
                      "type": "array",
                      "items": {
                        "type": "string"
                      }
                    },
                    "executability": {
                      "type": "object",
                      "properties": {
                        "isExecutable": {
                          "type": "boolean",
                          "example": true
                        },
                        "reasons": {
                          "type": "array",
                          "items": {
                            "type": "object",
                            "additionalProperties": false,
                            "properties": {
                              "models": {
                                "type": "string",
                                "example": "gemini-2.5-flash-image"
                              }
                            }
                          }
                        }
                      },
                      "additionalProperties": false
                    }
                  },
                  "additionalProperties": false
                }
              },
              "additionalProperties": false
            }
          },
          "totalCount": {
            "type": "integer",
            "example": 2
          },
          "pageInfo": {
            "type": "object",
            "properties": {
              "hasNextPage": {
                "type": "boolean",
                "example": false
              },
              "hasPreviousPage": {
                "type": "boolean",
                "example": false
              },
              "startCursor": {
                "type": "string",
                "example": "eyJjcmVhdGVkQXQiOiIyMDI1LTExLTI3VDA1OjEzOjIxLjg5NloiLCJha1VVSUQiOiI5NTZlOTU2NC0xOWY3LTQ5NjgtYjU2ZC0wNWMyYzU2NzcyNmYifQ=="
              },
              "endCursor": {
                "type": "string",
                "example": "eyJjcmVhdGVkQXQiOiIyMDI1LTExLTI3VDA1OjEzOjIxLjg5NloiLCJha1VVSUQiOiI5NTZlOTU2NC0xOWY3LTQ5NjgtYjU2ZC0wNWMyYzU2NzcyNmYifQ=="
              }
            },
            "additionalProperties": false
          }
        },
        "additionalProperties": false
      },
      "ApiError": {
        "type": "object",
        "title": "ApiError",
        "description": "API error response structure",
        "required": [
          "message"
        ],
        "properties": {
          "message": {
            "type": "string",
            "description": "Error message"
          },
          "path": {
            "type": "array",
            "items": {
              "type": "string"
            },
            "description": "Path to the field that caused the error"
          },
          "locations": {
            "type": "array",
            "items": {
              "type": "object",
              "properties": {
                "column": {
                  "type": "integer"
                },
                "line": {
                  "type": "integer"
                }
              }
            },
            "description": "Location information for the error"
          },
          "extensions": {
            "type": "object",
            "description": "Additional error details and context"
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