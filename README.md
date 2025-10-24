# RAG Study Chatbot

A full-stack mobile application featuring an AI-powered chatbot with Retrieval-Augmented Generation (RAG) capabilities. The application combines a React Native mobile frontend with a Python Flask backend, leveraging AWS services for authentication, storage, and AI inference.

## Overview

This project consists of two main components:

- **Mobile App** (`rag_study_chatbot/`): A cross-platform React Native mobile application built with Expo
- **Backend Server** (`server/`): A Python Flask REST API that interfaces with AWS services including Bedrock, DynamoDB, S3, and Cognito

## Features

### Mobile Application
- **User Authentication**: Secure sign-up and login via AWS Cognito
- **Real-time Chat Interface**: Intuitive chat UI with message streaming support
- **Chat History Management**: Save, view, and manage previous conversations
- **Message Operations**: Edit and delete messages with real-time updates
- **Model Switching**: Toggle between different AI models on the fly
- **File Attachments**: Upload and share images and documents in conversations
- **Document Viewer**: In-app document viewing capabilities
- **Profile Management**: User account management and settings

### Backend Services
- **RAG Implementation**: Knowledge base integration using AWS Bedrock
- **Multiple AI Models**: Support for various LLMs via AWS Bedrock
- **Document Processing**: PDF text extraction and analysis with AWS Textract
- **Image Processing**: Image handling and analysis capabilities
- **JWT Authentication**: Secure token-based authentication
- **Encrypted Storage**: Secure data encryption for sensitive information
- **S3 Integration**: File upload and retrieval from AWS S3
- **DynamoDB**: NoSQL database for chat history and user data

## Project Structure

```
study_chatbot/
├── rag_study_chatbot/          # React Native mobile app
│   ├── src/
│   │   ├── components/         # Reusable UI components
│   │   │   ├── auth/          # Authentication screens
│   │   │   ├── chat/          # Chat interface components
│   │   │   ├── screens/       # App screens
│   │   │   └── ui/            # General UI elements
│   │   ├── contexts/          # React contexts for state management
│   │   ├── navigation/        # Navigation configuration
│   │   ├── services/          # API service layer
│   │   └── types/             # TypeScript type definitions
│   ├── assets/                # Images, fonts, and static assets
│   ├── app.json               # Expo configuration
│   └── package.json           # Node dependencies
│
└── server/                     # Python Flask backend
    ├── core/                   # Core business logic
    │   ├── aws/               # AWS service integrations
    │   └── services/          # Application services
    ├── routes/                 # API route handlers
    ├── tests/                  # Test suite
    ├── docs/                   # API documentation
    ├── server.py              # Main Flask application
    ├── constants.py           # Configuration constants
    ├── encryption.py          # Encryption utilities
    ├── pdf_processing.py      # PDF processing logic
    └── requirements.txt       # Python dependencies
```

## Tech Stack

### Mobile App
- **Framework**: React Native 0.76.8 with Expo 54
- **Language**: TypeScript
- **Navigation**: React Navigation 7
- **State Management**: React Context API
- **Authentication**: AWS Cognito SDK
- **Storage**: AsyncStorage
- **HTTP Client**: Axios
- **UI Components**: React Native core components with custom styling

### Backend
- **Framework**: Flask 2.3+
- **Language**: Python 3.x
- **AWS Services**:
  - Bedrock (AI/ML models)
  - DynamoDB (Database)
  - S3 (File storage)
  - Cognito (Authentication)
  - Textract (Document processing)
- **AI Framework**: LangChain
- **Authentication**: JWT with PyJWT
- **Encryption**: Cryptography library

## Getting Started

### Prerequisites

#### Mobile App
- Node.js (v16 or higher)
- npm or yarn
- Expo CLI: `npm install -g expo-cli`
- iOS Simulator (macOS) or Android Emulator
- Expo account (for development builds)

#### Backend
- Python 3.8+
- pip
- AWS Account with configured credentials
- AWS services set up (Cognito, DynamoDB, S3, Bedrock)

### Installation

#### 1. Clone the Repository
```bash
git clone <repository-url>
cd study_chatbot
```

#### 2. Set Up the Backend

```bash
cd server

# Create and activate virtual environment (recommended)
python -m venv venv
source venv/bin/activate  # On Windows: venv\Scripts\activate

# Install dependencies
pip install -r requirements.txt

# Configure environment variables
cp .env.example .env
# Edit .env with your AWS credentials and configuration
```

Required environment variables:
- `AWS_REGION`
- `AWS_ACCESS_KEY_ID`
- `AWS_SECRET_ACCESS_KEY`
- `KNOWLEDGE_BASE_ID`
- `COGNITO_USER_POOL_ID`
- `COGNITO_CLIENT_ID`
- DynamoDB table names
- S3 bucket names

```bash
# Run the server
python server.py
```

#### 3. Set Up the Mobile App

```bash
cd rag_study_chatbot

# Install dependencies
npm install

# Configure environment variables
cp .env.example .env
# Edit .env with your backend API URL and AWS configuration

# Start the development server
npm start

# Run on specific platform
npm run ios      # iOS simulator (macOS only)
npm run android  # Android emulator
```

## Configuration

### Mobile App Configuration

Edit `app.json` to customize:
- App name and display name
- Bundle identifiers (iOS/Android)
- App icons and splash screens
- Permissions
- Build settings

### Backend Configuration

Edit `constants.py` for:
- Model configurations
- AWS service settings
- API endpoints
- Default values

## API Documentation

The backend provides RESTful endpoints for:

- **Authentication**: User registration, login, token refresh
- **Chat Management**: Create, delete, and retrieve chat sessions
- **Messages**: Send messages, retrieve history, edit/delete messages
- **File Operations**: Upload files, generate presigned URLs
- **Model Management**: Switch between AI models
- **User Profile**: Manage user account and settings

See `server/README.md` for detailed API documentation.

## Development

### Mobile App Scripts
```bash
npm start          # Start Expo development server
npm run android    # Build and run on Android
npm run ios        # Build and run on iOS
npm run web        # Run in web browser
```

### Running Tests
```bash
# Backend tests
cd server
pytest tests/

# Mobile app tests (if configured)
cd rag_study_chatbot
npm test
```

## Deployment

### Mobile App
The app uses Expo's EAS Build for creating production builds:

```bash
# Install EAS CLI
npm install -g eas-cli

# Configure EAS
eas build:configure

# Build for iOS
eas build --platform ios

# Build for Android
eas build --platform android
```

### Backend
Deploy the Flask backend to your preferred hosting service:
- AWS EC2
- AWS Elastic Beanstalk
- Heroku
- Docker container

Ensure all environment variables are properly configured in your production environment.

## Security Considerations

- All sensitive data is encrypted at rest
- JWT tokens are used for secure authentication
- Environment variables store sensitive configuration
- AWS IAM roles and policies control service access
- Input validation and sanitization on all endpoints

## Contributing

1. Fork the repository
2. Create a feature branch (`git checkout -b feature/amazing-feature`)
3. Commit your changes (`git commit -m 'Add some amazing feature'`)
4. Push to the branch (`git push origin feature/amazing-feature`)
5. Open a Pull Request

## License

MIT License

Copyright (c) 2025 John Lu

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT SHALL THE
AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM, DAMAGES OR OTHER
LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR OTHERWISE, ARISING FROM,
OUT OF OR IN CONNECTION WITH THE SOFTWARE OR THE USE OR OTHER DEALINGS IN THE
SOFTWARE.

## Acknowledgments

- AWS Bedrock for AI model access
- Expo team for the excellent React Native framework
- LangChain for RAG implementation support

## Support

For issues, questions, or contributions, please open an issue in the GitHub repository.
