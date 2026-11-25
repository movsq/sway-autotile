# Maintainer: Vojtěch Sedláček <https://github.com/movsq>

# Builds from the files next to this PKGBUILD (this checkout), not from a download:
#   makepkg            # -> sway-autotile-<ver>-<rel>-any.pkg.tar.zst here
#   pacman -U ./sway-autotile-*.pkg.tar.zst
# The tests need a headless sway and a terminal and take minutes, so they are not run here: run
# tests/run before building.

pkgname=sway-autotile
pkgver=0.1.0
pkgrel=1
pkgdesc='Autotiling for sway that removes the one-window containers its splits leave behind'
arch=('any')
url='https://github.com/movsq/sway-autotile'
license=('MIT')
depends=('python' 'sway')
source=('sway-autotile' 'LICENSE' 'README.md')
sha256sums=('SKIP' 'SKIP' 'SKIP')

package() {
  install -Dm755 sway-autotile "$pkgdir/usr/bin/sway-autotile"
  install -Dm644 LICENSE "$pkgdir/usr/share/licenses/$pkgname/LICENSE"
  install -Dm644 README.md "$pkgdir/usr/share/doc/$pkgname/README.md"
}
