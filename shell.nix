with import <nixpkgs> { };

let
  jishaku = { astunparse, braceexpand, click, importlib-metadata, setuptools
    , buildPythonPackage, fetchPypi, import_expression }:
    buildPythonPackage {
      pname = "jishaku";
      version = "2.3.2";

      src = fetchgit {
        url = "https://github.com/Gorialis/jishaku.git";
        rev = "d8e676f55a48e1ffad14e13e733debd4ab93eccb";
        sha256 = "sha256-axX1po5xWn2zvNzzsekPBBcbTnGwDVUFXH2BYqDiagI=";
      };

      propagatedBuildInputs =
        [ braceexpand click importlib-metadata setuptools import_expression ];

      doCheck = false;
    };

  discordExtMenus = { discordpy, buildPythonPackage }:
    buildPythonPackage {
      pname = "discord-ext-menus";
      version = "1.0.0-a";

      propagatedBuildInputs = [ discordpy ];

      src = fetchgit {
        url = "https://github.com/Rapptz/discord-ext-menus.git";
        rev = "fbb8803779373357e274e1540b368365fd9d8074";
        sha256 = "sha256-pUSMpCyIGXv8GtMNT6jX6QBwoMGHL0tt9xM0nnn3ZQA=";
      };

      doCheck = false;
    };

  import_expression = { buildPythonPackage, astunparse, fetchPypi }:
    buildPythonPackage rec {
      pname = "import_expression";
      version = "1.1.4";
      src = fetchPypi {
        inherit pname version;
        sha256 = "sha256-BghqarO/pSixxHjmM9at8rOpkOMUQPZAGw8+oSsGWak=";
      };
      propagatedBuildInputs = [ astunparse ];
      doCheck = false;
    };
in (python39.withPackages (pythonPkgs:
  with pythonPkgs; [
    discordpy
    uvloop
    pillow
    aiosqlite
    fuzzywuzzy
    pylast
    (discordExtMenus { inherit discordpy buildPythonPackage; })

    (buildPythonPackage rec {
      pname = "lifesaver";
      version = "0.0.0";

      propagatedBuildInputs = [
        (jishaku {
          inherit astunparse braceexpand click importlib-metadata setuptools
            buildPythonPackage fetchPypi;
          import_expression = import_expression {
            inherit buildPythonPackage astunparse fetchPypi;
          };
        })
        click
        discordpy
        ruamel-yaml
      ];

      src = fetchgit {
        url = "https://github.com/slice/lifesaver.git";
        rev = "00c38112a512efd964cbbf0533096eff0a29f79f";
        sha256 = "sha256-9usGgZyAIfCKw21U16TNVfNfwBkQkbgdOB2NZAyTj9I=";
      };

      doCheck = false;
    })
  ])).env
