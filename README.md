# ShopperB2B Backend

This repository contains the backend services for the ShopperB2B application, including:

1. **User Service**: Handles user authentication and management
2. **Cart Service**: Manages shopping carts using Redis
3. **Product Service**: Handles product and category related operations

## Architecture

- **User Service**: FastAPI application with PostgreSQL database
- **Cart Service**: FastAPI application with Redis for cart storage
- Both services use JWT for authentication
- **Product Service**: FastAPI application for all product related operations

## Getting Started

### Prerequisites

- Docker and Docker Compose
- Git

### Running the Services

1. Clone the repository:

   ```
   git clone <repository-url>
   cd ShopperB2Bbackend
   ```

2. Start all services:

   ```
   docker compose up -d
   ```

3. Access the services:
   - User Service API: http://localhost:8000
   - Cart Service API: http://localhost:8001
   - Product Service API: http://localhost:8002 
   - PostgreSQL: localhost:5432
   - Redis: localhost:6379

### Running in Development Mode

To run the services in development mode with live logs:

1. Start all services with logs visible:

   ```
   docker compose up
   ```

2. To run a specific service:

   ```
   docker compose up user-service
   ```

   or

   ```
   docker compose up cart-service
   ```

3. To rebuild and restart a service after code changes:
   ```
   docker compose up -d --build user-service
   ```
   or
   ```
   docker compose up -d --build cart-service
   ```

### API Documentation

Once the services are running, you can access the API documentation at:

- User Service: http://localhost:8000/docs
- Cart Service: http://localhost:8001/docs
- Product Service: http://localhost:8002/docs

## Service Endpoints

### User Service

- `POST /users/signup`: Register a new user
- `POST /users/login`: Login and get access token
- `POST /users/refresh`: Refresh access token
- `GET /users/me`: Get current user info
- `PUT /users/me`: Update user info
- `PUT /users/me/password`: Update password

### Cart Service

- `GET /cart`: Get cart contents
- `POST /cart/items/{product_id}`: Add item to cart
- `PUT /cart/items/{product_id}`: Update item quantity
- `DELETE /cart/items/{product_id}`: Remove item from cart
- `DELETE /cart`: Clear cart

### Product Service

- `GET /products?query={query}&limit={limit}&page={page}`: Get all matching products for the query
- `GET /product/{product_id}`: Get the required product
- `GET /categories`: Gets all Amazon categories
- `GET /category/{category_id}`: Gets the category name, queries it in algolia and gets the results

## Development

To make changes to the services:

1. The services are set up with volume mounts, so changes to the code will be reflected immediately
2. For database changes, you may need to restart the services

## Stopping the Services

To stop all services:

```
docker compose down
```

To stop and remove all data (including databases):

```
docker compose down -v
```
