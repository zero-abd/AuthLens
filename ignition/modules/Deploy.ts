import { buildModule } from "@nomicfoundation/hardhat-ignition/modules";

// This is an Ignition 'Module'. It defines the deployment steps.
const VideoAuthModule = buildModule("VideoAuthModule", (m) => {
  // This line tells Ignition to deploy our 'VideoAuth' contract.
  const videoAuth = m.contract("VideoAuth");

  // We return the deployed contract instance.
  return { videoAuth };
});

export default VideoAuthModule;