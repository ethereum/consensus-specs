let dapptools = builtins.fetchGit {
    url = "https://github.com/dapphub/dapptools.git";
    rev = "11dcefe1f03b0acafe76b4d7d54821ef6bd63131";
  };
    nixpkgs = builtins.fetchGit {
      url = "https://github.com/nixos/nixpkgs";
      ref = "release-19.03";
      rev = "f1707d8875276cfa110139435a7e8998b4c2a4fd";
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
