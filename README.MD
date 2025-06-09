
# Online Cinema - FastAPI Project

## 📋 Project Overview

Online Cinema is a comprehensive digital platform built with FastAPI that allows users to browse, purchase, and manage access to movies and video content. The platform features user authentication, movie catalog management, shopping cart functionality, payment processing, and role-based access control.

## 🚀 Key Features

### User Management
- **Registration & Authentication**: Email-based registration with account activation
- **JWT Token Management**: Access and refresh token implementation
- **Password Management**: Secure password reset and change functionality
- **Role-Based Access**: User, Moderator, and Admin roles with different permissions
- **User Profiles**: Extended user information with avatars and personal details

### Movie Catalog
- **Comprehensive Movie Database**: Movies with detailed information (genre, directors, stars, ratings)
- **Advanced Search & Filtering**: Search by title, description, actor, director with multiple filters
- **User Interactions**: Comments, ratings (1-10 scale), and favorites
- **Notifications**: Real-time notifications for comment replies and likes
- **Content Management**: Full CRUD operations for moderators

### Shopping & Payments
- **Shopping Cart**: Add/remove movies, view cart contents, validate purchases
- **Order Management**: Place orders, track order history, cancel pending orders
- **Stripe Integration**: Secure payment processing with webhook validation
- **Purchase Validation**: Prevent duplicate purchases, ensure movie availability

### Technical Features
- **Docker Containerization**: Complete Docker and Docker Compose setup
- **CI/CD Pipeline**: GitHub Actions for automated testing and deployment
- **API Documentation**: Comprehensive Swagger/OpenAPI documentation
- **Background Tasks**: Celery integration for email sending and cleanup tasks
- **File Storage**: MinIO integration for avatar and media storage

## 🛠️ Tech Stack

- **Backend**: FastAPI (Python)
- **Database**: PostgreSQL
- **Authentication**: JWT tokens
- **Payment Processing**: Stripe
- **Task Queue**: Celery + Redis
- **File Storage**: MinIO
- **Containerization**: Docker & Docker Compose
- **Dependency Management**: Poetry
- **Testing**: pytest
- **CI/CD**: GitHub Actions
- **Documentation**: Swagger/OpenAPI

## 📁 Project Structure

```
online-cinema/
├── src/
│   ├── routes/                 # API endpoints
│   │   ├── accounts.py         # Authentication & user management
│   │   ├── movies.py           # Movie catalog operations
│   │   ├── shopping_cart.py    # Shopping cart functionality
│   │   ├── orders.py           # Order management
│   │   └── payments.py         # Payment processing
│   ├── database/
│   │   ├── models/             # SQLAlchemy models
│   │   ├── migrations/         # Alembic database migrations
│   │   └── seed_data/          # Initial data (CSV files)
│   ├── schemas/                # Pydantic request/response models
│   ├── security/               # Authentication & authorization
│   ├── notifications/          # Email templates & services
│   ├── celery_/                # Background tasks
│   ├── stripe_service/         # Payment integration
│   ├── tests/                  # Test suites
│   │   ├── test_integration/   # Integration tests
│   │   ├── test_unit/          # Unit tests
│   │   └── test_e2e/           # End-to-end tests
│   └── main.py                 # FastAPI application entry point
├── commands/                   # Deployment & setup scripts
├── configs/                    # Configuration files (nginx)
├── docker/                     # Docker configurations
├── docker-compose-*.yml        # Docker compose files (dev/prod/test)
├── pyproject.toml              # Poetry dependencies
└── README.md
```

## 🔧 Installation & Setup

### Prerequisites
- Docker & Docker Compose
- Poetry (for local development)
- Python 3.11+
- Stripe account (for payment processing)

### Quick Start with Docker

1. **Clone the repository**
   ```bash
   git clone <repository-url>
   cd online-cinema
   ```

2. **Stripe Configuration**
   
   a) **Create Stripe Account**
   - Sign up at [stripe.com](https://stripe.com)
   - Go to **Developers** → **API Keys**
   - Copy your **Publishable key** and **Secret key**
   
   b) **Set up Webhooks**
   - In Stripe Dashboard: **Developers** → **Webhooks**
   - Click **Add endpoint**
   - URL: `https://your-domain.com/api/v1/webhooks/stripe`
   - Events: Select `payment_intent.succeeded` and `payment_intent.payment_failed`
   - Copy the **Webhook signing secret**
   
   c) **Install Stripe CLI** (for local development)
   ```bash
   # macOS
   brew install stripe/stripe-cli/stripe
   
   # Windows
   # Download from https://github.com/stripe/stripe-cli/releases
   
   # Linux
   wget https://github.com/stripe/stripe-cli/releases/latest/download/stripe_linux_x86_64.tar.gz
   tar -xvf stripe_linux_x86_64.tar.gz
   sudo mv stripe /usr/local/bin
   ```
   
   d) **Login to Stripe CLI**
   ```bash
   stripe login
   stripe listen --forward-to localhost:8000/api/v1/webhooks/stripe
   # Copy the webhook signing secret from output
   ```

3. **Environment Configuration**
   ```bash
   cp .env.example .env
   # Edit .env with your configuration
   ```

4. **Launch all services**
   ```bash
   docker-compose -f docker-compose-dev.yml up --build
   ```

5. **Access the application**
   - API: http://localhost:8000
   - Documentation: http://localhost:8000/docs


## 🔐 Environment Variables

Rename .env.sample as .env and fill all variables with your value.

## 🗄️ Database Schema

### User Management
- **users**: Core user information
- **user_profiles**: Extended user profiles
- **user_groups**: Role definitions (User, Moderator, Admin)
- **activation_tokens**: Email activation tokens
- **password_reset_tokens**: Password reset tokens
- **refresh_tokens**: JWT refresh tokens

### Movie Catalog
- **movies**: Movie information and metadata
- **genres**: Movie genres
- **directors**: Movie directors
- **stars**: Movie actors/actresses
- **certifications**: Movie ratings (PG, R, etc.)
- **movie_genres**: Many-to-many relationship
- **movie_directors**: Many-to-many relationship
- **movie_stars**: Many-to-many relationship

### Shopping & Orders
- **carts**: User shopping carts
- **cart_items**: Items in shopping carts
- **orders**: User orders
- **order_items**: Items in orders
- **payments**: Payment transactions
- **payment_items**: Individual payment items

## 🔄 API Endpoints

### Authentication
- `POST /api/v1/accounts/register/` - User registration
- `POST /api/v1/accounts/login` - User login
- `POST /api/v1/accounts//logout` - User logout
- `POST /api/v1/accounts/refresh` - Refresh access token
- `POST /api/v1/accounts/activate/` - Activate account
- `POST /api/v1/accounts/password-reset/request/` - Request a password reset token
- `POST /api/v1/accounts/reset-password/complete/` - Reset User Password
- `POST /api/v1/accounts/users/{user_id}/group/` - Set new User Password
- `PATCH /api/v1/accounts/change-password/` - Request to change user group
- `POST /api/v1/accounts/new_activation_token/` - Request to send a new activation token

### Movies
- `GET /api/v1//theater/movies/` - List movies with filtering and pagination
- `GET /api/v1//theater/movies/{id}/` - Get movie details
- `POST /api/v1//theater/movies/` - Create movie (Moderator+)
- `PATCH /api/v1//theater/movies/{id}/` - Update movie (Moderator+)
- `DELETE /api/v1//theater/movies/{id}/` - Delete movie (Moderator+)
### Opinions
- `POST /api/v1/opinions/movies/favorite/{movie_id}/` - Add movie to favorite
- `DELETE /api/v1/opinions/movies/favorite/{movie_id}/` - Remove movie from favorite
- `GET /api/v1/opinions/movies/favorite/{movie_id}/` - Remove movie from favorite
- `GET /api/v1/opinions/movies/favorite/` - List favorite movies.
- `POST /api/v1/opinions/movies/comment/{movie_id}/` - Add commentary to movie
- `POST /api/v1/opinions/movies/comment/reply/{comment_id}/` - Reply no the comment
- `GET /api/v1/opinions/movies/{movie_id}/rate` - Rate movie

### Shopping Cart
- `GET /api/v1/cart/items/` - Get cart contents
- `POST /api/v1/cart/items/{movie_id}/` - Add item to cart- 
- `DELETE /api/v1/cart/items/{movie_id}/` - Remove item from cart
- `DELETE /api/v1/cart/items/` - Clear cart
- `GET /api/v1/cart/{user_id}/` - Get cart contents (Admin)

### Orders
- `GET /api/v1/orders/list/` - List user orders (Owner or Admin)
- `POST /api/v1/orders/place/` - Create order from cart
- `PATCH /api/v1/orders/cancel/{order_id}/` - Cancel order (change status)

### Payments
- `POST /api/v1/payments/create-intent` - Create payment intent
- `POST /api/v1/payments/webhook` - Stripe webhook handler
- `GET /api/v1/payments/` - Payments history
- `GET /api/v1/payments/all/` - List payments with filtering and pagination (Moderator+)

## 🧪 Testing

### Test categories
- **Unit Tests**: Data validation, utility functions, business rules
- **Integration Tests**: Database interactions, authentication workflows
- **Functional Tests**: End-to-end user scenarios


#### **1️⃣ Running Unit and Integration Tests (Without Docker)**
You can run the unit and integration tests **directly** using `pytest`:

```bash
pytest src/tests/test_integration/
```
```bash
pytest src/tests/test_unit/
```
This will execute **only the integration and uni tests**, ensuring that your API logic functions correctly **without spinning up Docker containers**.

#### **2️⃣ Running End-to-End (E2E) Tests**
To run the full **E2E test suite**, you need to start the test environment using Docker:

```bash
docker-compose -f docker-compose-tests.yml up --build
```
This will spin up all necessary services (database, MinIO, MailHog, FastAPI instance) and execute the **end-to-end tests** inside the test container.

### **Test Results**
- The test logs will **highlight any failures** and discrepancies between your implementation and expected behavior.
- Use the error messages from the test output to **fix issues and adjust your code accordingly**.

By following these steps, you can ensure your implementation is correct and fully aligned with the **Movie Theater API** project requirements.

## 🚀 CI/CD Pipeline

The project includes GitHub Actions workflows for:

- **Code Quality**: Linting with flake8/black
- **Testing**: Automated test execution with pytest
- **Deployment**: Automatic deployment to AWS EC2


## 🔒 Security Features

- JWT-based authentication with refresh tokens
- Password complexity validation
- Email verification for account activation
- Role-based access control
- Input validation and sanitization

## 🎯 User Roles & Permissions

### User
- Browse movie catalog
- Manage personal profile
- Add movies to cart and favorites
- Place orders and make payments
- Rate and comment on movies

### Moderator
- All User permissions
- CRUD operations on movies, genres, actors
- View sales analytics
- Manage movie content

### Admin
- All Moderator permissions
- User management
- Change user roles
- Manual account activation
- System administration

## 📝 API Documentation

Access the interactive API documentation at:
- Swagger UI: `http://localhost:8000/docs`
- ReDoc: `http://localhost:8000/redoc`



To try API functionality, go to the IP address http://3.78.15.97/docs#/  
- user: Mate_user 
- password: FKVOD8UJ1VZNAIV

## 📜 License

This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

