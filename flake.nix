{
  inputs = {
    lifesaver.url = "path:/Users/slice/src/prj/lifesaver";
    flake-utils.url = "github:numtide/flake-utils";
  };

  outputs = { lifesaver, flake-utils, ... }:
    flake-utils.lib.eachDefaultSystem (system:
      lifesaver.lib.${system}.mkFlake ({ python, ... }:
        let
          discord-ext-menus = python.pkgs.buildPythonPackage {
            pname = "discord-ext-menus";
            version = "1.0.0-a";
            src = builtins.fetchGit {
              url = "https://github.com/Rapptz/discord-ext-menus";
              ref = "master";
              rev = "8686b5d1bbc1d3c862292eb436ab630d6e9c9b53";
            };
            propagatedBuildInputs = [ python.pkgs.discordpy ];
            doCheck = false;
            pythonImportsCheck = [ "discord.ext.menus" ];
          };
        in {
          name = "s2";
          path = ./.;
          propagatedBuildInputs = with python.pkgs; [
            pillow
            fuzzywuzzy
            aiosqlite
            pylast
            discord-ext-menus
          ];
          pythonPackageOptions.format = "pyproject";
        }));
}
