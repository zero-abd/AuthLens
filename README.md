# AuthLens: Where Evidence Meets Certainty

<p align="left"><i>Built for HackTX 2025</i></p>

**Live demo: https://authlens-app.vercel.app**. Verify any video against the deployed Sepolia contract right in your browser, or register one from your own MetaMask wallet. No backend or keys are needed for the demo. The web app lives in the `AuthLens-Frontend` submodule ([zero-abd/AuthLens-Frontend](https://github.com/zero-abd/AuthLens-Frontend), branch `main`).

## 📖 Overview

AuthLens is a blockchain-powered video authentication platform that ensures the integrity and verifiability of video evidence. By storing cryptographic hashes of video chunks on the Ethereum blockchain, AuthLens provides tamper-proof verification of video authenticity, timestamps, and ownership.

### Key Features

- 🔐 **Blockchain-Backed Verification**: Store cryptographic hashes on Ethereum for immutable proof
- ⏱️ **Timestamp Validation**: Track exact recording times for each video chunk
- 🎥 **Chunked Processing**: Process videos in 1-minute segments for efficient handling
- 🔍 **Instant Verification**: Quickly verify if a video exists on the blockchain
- 🌐 **Decentralized Trust**: Leverage blockchain technology for transparent, tamper-proof records

## 🏗️ Project Structure

```
AuthLens/
├── contracts/              # Solidity smart contracts
│   └── VideoAuth.sol      # Main video authentication contract
├── backend/               # Python FastAPI server
│   ├── main.py           # API endpoints
│   ├── test_client.py    # Testing script
│   └── requirements.txt  # Python dependencies
├── AuthLens-Frontend/    # React frontend application
├── ignition/             # Hardhat deployment modules
├── test/                 # Smart contract tests
└── hardhat.config.ts     # Hardhat configuration
```

## 🚀 Getting Started

### Prerequisites

- Node.js (v18 or higher)
- Python (v3.8 or higher)
- MetaMask wallet with Sepolia testnet ETH
- Alchemy or Infura account for RPC access

---

## 🔗 Blockchain Setup

### 1. Install Dependencies

```shell
npm install
```

### 2. Configure Environment Variables

Create a `.env` file in the root directory:

```env
SEPOLIA_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/YOUR_API_KEY
PRIVATE_KEY=your_wallet_private_key_here
```

> ⚠️ **Security Note**: Never commit your `.env` file or share your private key!

### 3. Deploy Smart Contract to Sepolia

Deploy the VideoAuth contract to Sepolia testnet:

```shell
npx hardhat ignition deploy ignition/modules/Deploy.ts --network sepolia
```

After deployment, note the contract address displayed in the console. You'll need this for the backend configuration.

### 4. Verify Deployment (Optional)

Check the deployment status:

```shell
npx hardhat ignition status chain-11155111
```

### 5. Run Smart Contract Tests

To verify the contract functionality:

```shell
npx hardhat test
```

---

## 🐍 Backend Setup

### 1. Navigate to Backend Directory

```shell
cd backend
```

### 2. Install Python Dependencies

```shell
pip install -r requirements.txt
```

### 3. Configure Backend Environment

Create a `.env` file in the `backend` directory:

```env
SEPOLIA_RPC_URL=https://eth-sepolia.g.alchemy.com/v2/YOUR_API_KEY
PRIVATE_KEY=your_wallet_private_key_here
CONTRACT_ADDRESS=your_deployed_contract_address_here
```

### 4. Copy Contract ABI

Copy the compiled contract ABI to the backend:

```shell
copy ..\artifacts\contracts\VideoAuth.sol\VideoAuth.json VideoAuth.json
```

Or on macOS/Linux:

```shell
cp ../artifacts/contracts/VideoAuth.sol/VideoAuth.json VideoAuth.json
```

### 5. Start the API Server

```shell
python main.py
```

The server will start at `http://localhost:8000`

### 6. Verify Server is Running

Open your browser and navigate to:
- API Documentation: `http://localhost:8000/docs`
- Health Check: `http://localhost:8000/`

---

## 🧪 Testing the Backend

### Run the Test Client

The project includes a comprehensive test script to verify all functionality:

```shell
python test_client.py
```

This test script will:
1. ✅ Check server health
2. 📤 Upload video chunks with timestamps
3. 🔍 Verify videos on the blockchain
4. 📥 Retrieve videos from specific time ranges
5. ⏰ Test time range queries

### Manual API Testing

You can also test individual endpoints using curl or the interactive API docs at `http://localhost:8000/docs`:

#### Upload a Video Chunk

```shell
curl -X POST "http://localhost:8000/api/video/process-chunk?start_time=2025-01-15T10:00:00&end_time=2025-01-15T10:01:00" ^
  -F "video=@path/to/your/video.mp4"
```

#### Verify a Video

```shell
curl -X POST "http://localhost:8000/api/video/verify" ^
  -F "video=@path/to/your/video.mp4"
```

#### Get Videos in Time Range

```shell
curl "http://localhost:8000/api/video/range?start_time=2025-01-15T10:00:00&end_time=2025-01-15T11:00:00"
```

---

## 🎨 Frontend Setup

### 1. Navigate to Frontend Directory

```shell
cd AuthLens-Frontend
```

### 2. Install Dependencies

```shell
npm install
```

### 3. Start Development Server

```shell
npm start
```

The frontend will open at `http://localhost:3000`

---

## 📚 API Endpoints

| Method | Endpoint | Description |
|--------|----------|-------------|
| GET | `/` | Health check |
| POST | `/api/video/process-chunk` | Upload and process video chunk |
| POST | `/api/video/verify` | Verify if video exists on blockchain |
| GET | `/api/video/range` | Get videos in time range |

---

## 🔒 Smart Contract Details

### VideoAuth.sol

The `VideoAuth` contract provides two main functions:

- **storeHash(bytes32 _videoHash)**: Stores a video hash on the blockchain
- **verifyHash(bytes32 _videoHash)**: Verifies if a hash exists and returns the uploader address

---

## 🛠️ Troubleshooting

### Common Issues

**Problem**: Contract deployment fails
- **Solution**: Ensure you have enough Sepolia ETH in your wallet (get free testnet ETH from [Sepolia faucet](https://sepoliafaucet.com/))

**Problem**: Backend can't connect to contract
- **Solution**: Verify the CONTRACT_ADDRESS in your backend `.env` file matches the deployed contract address

**Problem**: Transaction reverts with "hash already registered"
- **Solution**: This video hash already exists on the blockchain - this is expected behavior for duplicate videos

---

## 📄 License

This project is licensed under the MIT License.

---

## 👥 Team

Built with ❤️ for HackTX 2025

---

## 🙏 Acknowledgments

- Ethereum Foundation for blockchain infrastructure
- Hardhat for development tools
- FastAPI for the backend framework

After setting the variable, you can run the deployment with the Sepolia network:

```shell
npx hardhat ignition deploy --network sepolia ignition/modules/Counter.ts
```
