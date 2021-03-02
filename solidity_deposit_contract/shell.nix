let dapptools = builtins.fetchGit {
    url = "https://github.com/dapphub/dapptools.git";
    rev = "bbc2b483f94908bd0380de967361d3b21fb3d392";
  };
    nixpkgs = builtins.fetchGit {
      url = "https://github.com/nixos/nixpkgs";
      ref = "release-20.03";
      rev = "5272327b81ed355bbed5659b8d303cf2979b6953";
  };
  pkgs-for-dapp = import nixpkgs {
    overlays = [
      (import (dapptools + /overlay.nix))
    ];
  };
in
pkgs-for-dapp.mkShell {
  buildInputs = [ pkgs-for-dapp.dapp pkgs-for-dapp.solc pkgs-for-dapp.hevm ];
}
