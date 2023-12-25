{pkgs}: {
  deps = [
    pkgs.imagemagick
    pkgs.zlib
    pkgs.tk
    pkgs.tcl
    pkgs.openjpeg
    pkgs.libxcrypt
    pkgs.libwebp
    pkgs.libtiff
    pkgs.libjpeg
    pkgs.libimagequant
    pkgs.lcms2
    pkgs.freetype
    pkgs.postgresql
  ];
  env = {
    PYTHON_LD_LIBRARY_PATH = pkgs.lib.makeLibraryPath [
      pkgs.zlib
      pkgs.tk
      pkgs.tcl
      pkgs.openjpeg
      pkgs.libxcrypt
      pkgs.libwebp
      pkgs.libimagequant
      pkgs.freetype
    ];
  };
}