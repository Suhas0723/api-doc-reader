export const SAMPLES = {
  minimal: `openapi: "3.0.0"
info:
  title: User API
  version: "1.0"
paths:
  /users:
    get:
      summary: Get
      responses:
        "200":
          description: OK
    post:
      summary: Create
      requestBody:
        content:
          application/json:
            schema:
              type: object
      responses:
        "200":
          description: OK
  /users/{id}:
    get:
      summary: Get user
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
      responses:
        "200":
          description: OK
        "404":
          description: Not found
    delete:
      summary: Delete
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
      responses:
        "200":
          description: OK`,

  good: `openapi: "3.0.0"
info:
  title: Payment Processing API
  version: "2.1.0"
  description: >
    Processes payment transactions, manages refunds, and retrieves
    transaction history for merchant accounts. All amounts in cents (USD).
paths:
  /transactions:
    post:
      operationId: createTransaction
      summary: Create a payment transaction
      description: >
        Initiates a new payment transaction for a given merchant. The
        transaction is processed synchronously; a 200 response confirms
        the charge was captured. Use idempotency-key header to safely
        retry failed requests without duplicate charges.
      security:
        - bearerAuth: []
      requestBody:
        required: true
        content:
          application/json:
            schema:
              type: object
              required: [amount, currency, source]
              properties:
                amount:
                  type: integer
                  description: "Charge amount in cents (e.g. 1099 = $10.99)"
                  minimum: 50
                currency:
                  type: string
                  description: "ISO 4217 currency code (e.g. USD, EUR)"
                source:
                  type: string
                  description: "Tokenized payment method ID from client-side SDK"
      responses:
        "200":
          description: Transaction created and funds captured
          content:
            application/json:
              schema:
                type: object
                properties:
                  id:
                    type: string
                    description: Unique transaction ID (txn_*)
                  status:
                    type: string
                    enum: [succeeded, pending, failed]
        "400":
          description: Invalid request (missing fields, below minimum amount)
        "401":
          description: Missing or invalid bearer token
        "422":
          description: Card declined or payment method invalid`,

  smelly: `openapi: "3.0.0"
info:
  title: API
  version: "1"
paths:
  /data:
    get:
      summary: Get data
      description: Gets the data from the system. This endpoint retrieves data. You can use this endpoint to get data. The data is returned in JSON format. This is the main endpoint for getting data from our system which stores data. Data retrieval is the primary function.
      responses:
        "200":
          description: Success
  /process:
    post:
      summary: Do processing
      description: Processes things
      requestBody:
        content:
          application/json:
            schema:
              type: object
              properties:
                input:
                  type: string
                flag:
                  type: boolean
                mode:
                  type: string
      responses:
        "200":
          description: Done
  /items/{id}/sub/{subId}/details:
    get:
      summary: Get item sub-resource details and configuration and metadata and other info
      description: "This endpoint handles authentication AND returns items AND manages state AND logs activity. Returns details about the item. Also handles sub-resources. Note: deprecated but still works. See /v2/items for new version. Auth: pass token in header OR query param OR cookie."
      parameters:
        - name: id
          in: path
          required: true
          schema:
            type: string
        - name: subId
          in: path
          required: true
          schema:
            type: string
      responses:
        "200":
          description: Returns the thing
  /delete:
    post:
      summary: Delete
      description: Deletes stuff
      responses:
        "200":
          description: OK`
};
