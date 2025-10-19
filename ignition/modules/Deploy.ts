import { buildModule } from "@nomicfoundation/hardhat-ignition/modules";

const VideoAuthModule = buildModule("VideoAuthModule", (m) => {
  const videoAuth = m.contract("VideoAuth");
  return { videoAuth };
});

export default VideoAuthModule;