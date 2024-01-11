# Fedora spec file for php-pecl-xdebug3
#
# Copyright (c) 2010-2021 Remi Collet
# Copyright (c) 2006-2009 Christopher Stone
#
# License: MIT
# http://opensource.org/licenses/MIT
#
# Please, preserve the changelog entries
#

%bcond_without      tests

# we don't want -z defs linker flag
%undefine _strict_symbol_defs_build

%global pecl_name  xdebug
%global with_zts   0%{!?_without_zts:%{?__ztsphp:1}}
%global gh_commit  52911afee0d66f4569d71d25bb9532c8fab9d5f5
%global gh_short   %(c=%{gh_commit}; echo ${c:0:7})

# version/release
%global upstream_version 3.1.2
#global upstream_prever  RC1
#global upstream_lower   rc1

# XDebug should be loaded after opcache
%global ini_name  15-%{pecl_name}.ini

Name:           php-pecl-xdebug3
Summary:        Provides functions for function traces and profiling
Version:        %{upstream_version}%{?upstream_prever:~%{upstream_lower}}
Release:        1%{?dist}
Source0:        https://github.com/%{pecl_name}/%{pecl_name}/archive/%{gh_commit}/%{pecl_name}-%{upstream_version}%{?upstream_prever}-%{gh_short}.tar.gz

# The Xdebug License, version 1.01
# (Based on "The PHP License", version 3.0)
License:        BSD
URL:            https://xdebug.org/

BuildRequires:  gcc
BuildRequires:  make
BuildRequires:  php-devel >= 7.2
BuildRequires:  php-pear
BuildRequires:  php-simplexml
BuildRequires:  libtool
BuildRequires:  php-soap

Requires:       php(zend-abi) = %{php_zend_api}
Requires:       php(api) = %{php_core_api}

Provides:       php-%{pecl_name}              = %{version}
Provides:       php-%{pecl_name}%{?_isa}      = %{version}
Provides:       php-pecl(Xdebug)              = %{version}
Provides:       php-pecl(Xdebug)%{?_isa}      = %{version}

%if 0%{?fedora} >= 35 || 0%{?rhel} >= 9 || "%{php_version}" > "8.0"
Obsoletes:     php-pecl-%{pecl_name}          < 3
Provides:      php-pecl-%{pecl_name}          = %{version}-%{release}
Provides:      php-pecl-%{pecl_name}%{?_isa}  = %{version}-%{release}
%else
# A single version can be installed
Conflicts:     php-pecl-%{pecl_name}          < 3
%endif

%description
The Xdebug extension helps you debugging your script by providing a lot of
valuable debug information. The debug information that Xdebug can provide
includes the following:

* stack and function traces in error messages with:
  o full parameter display for user defined functions
  o function name, file name and line indications
  o support for member functions
* memory allocation
* protection for infinite recursions

Xdebug also provides:

* profiling information for PHP scripts
* code coverage analysis
* capabilities to debug your scripts interactively with a debug client

Documentation: https://xdebug.org/docs/


%prep
%setup -qc
mv %{pecl_name}-%{gh_commit} NTS
mv NTS/package.xml .

sed -e '/LICENSE/s/role="doc"/role="src"/' -i package.xml

cd NTS
# ignore tests relying on DNS
find tests -type f -exec grep -q 'xdebug.client_host=' {} \; -delete -print
# ignore test with erratic result
rm tests/debugger/start_with_request_default_no_env.phpt

# Check extension version
ver=$(sed -n '/XDEBUG_VERSION/{s/.* "//;s/".*$//;p}' php_xdebug.h)
if test "$ver" != "%{upstream_version}%{?upstream_prever}%{?gh_date:-dev}"; then
   : Error: Upstream XDEBUG_VERSION version is ${ver}, expecting %{upstream_version}%{?upstream_perver}%{?gh_date:-dev}.
   exit 1
fi
cd ..

%if %{with_zts}
# Duplicate source tree for NTS / ZTS build
cp -pr NTS ZTS
%endif

cat << 'EOF' | tee %{ini_name}
; Enable xdebug extension module
zend_extension=%{pecl_name}.so

; Configuration
; See https://xdebug.org/docs/all_settings

EOF
sed -e '1d' NTS/%{pecl_name}.ini >>%{ini_name}


%build
cd NTS
%{_bindir}/phpize
%configure \
    --enable-xdebug  \
    --with-php-config=%{_bindir}/php-config
make %{?_smp_mflags}

%if %{with_zts}
cd ../ZTS
%{_bindir}/zts-phpize
%configure \
    --enable-xdebug  \
    --with-php-config=%{_bindir}/zts-php-config
make %{?_smp_mflags}
%endif


%install
# install NTS extension
make -C NTS install INSTALL_ROOT=%{buildroot}

# install package registration file
install -Dpm 644 package.xml %{buildroot}%{pecl_xmldir}/%{name}.xml

# install config file
install -Dpm 644 %{ini_name} %{buildroot}%{php_inidir}/%{ini_name}

%if %{with_zts}
# Install ZTS extension
make -C ZTS install INSTALL_ROOT=%{buildroot}

install -Dpm 644 %{ini_name} %{buildroot}%{php_ztsinidir}/%{ini_name}
%endif

# Documentation
for i in $(grep 'role="doc"' package.xml | sed -e 's/^.*name="//;s/".*$//')
do
  [ -f NTS/contrib/$i ] && j=contrib/$i || j=$i
  install -Dpm 644 NTS/$j %{buildroot}%{pecl_docdir}/%{pecl_name}/$j
done


%check
# Shared needed extensions
modules=""
for mod in simplexml; do
  if [ -f %{php_extdir}/${mod}.so ]; then
    modules="$modules -d extension=${mod}.so"
  fi
done

# only check if build extension can be loaded
%{_bindir}/php \
    --no-php-ini \
    --define zend_extension=%{buildroot}%{php_extdir}/%{pecl_name}.so \
    --modules | grep Xdebug

%if %{with_zts}
%{_bindir}/zts-php \
    --no-php-ini \
    --define zend_extension=%{buildroot}%{php_ztsextdir}/%{pecl_name}.so \
    --modules | grep Xdebug
%endif

%if %{with tests}
cd NTS
: Upstream test suite NTS extension

%ifarch %{ix86}
# see https://bugs.xdebug.org/view.php?id=2048
rm tests/base/bug02036.phpt
%endif

# bug00886 is marked as slow as it uses a lot of disk space
TEST_OPTS="-q -x --show-diff"

TEST_PHP_EXECUTABLE=%{_bindir}/php \
TEST_PHP_ARGS="-n $modules -d zend_extension=%{buildroot}%{php_extdir}/%{pecl_name}.so" \
REPORT_EXIT_STATUS=1 \
%{__php} -n run-xdebug-tests.php $TEST_OPTS
%else
: Test suite disabled
%endif


%files
%license NTS/LICENSE
%doc %{pecl_docdir}/%{pecl_name}
%{pecl_xmldir}/%{name}.xml

%config(noreplace) %{php_inidir}/%{ini_name}
%{php_extdir}/%{pecl_name}.so

%if %{with_zts}
%config(noreplace) %{php_ztsinidir}/%{ini_name}
%{php_ztsextdir}/%{pecl_name}.so
%endif


%changelog
* Fri Dec 10 2021 Remi Collet <rcollet@redhat.com> - 3.1.2-1
- update to 3.1.2 rhbz#2030322

* Mon Aug 09 2021 Mohan Boddu <mboddu@redhat.com> - 3.0.4-5
- Rebuilt for IMA sigs, glibc 2.34, aarch64 flags
  Related: rhbz#1991688

* Thu Jul  8 2021 Remi Collet <rcollet@redhat.com> - 3.0.4-4
- ignore tests relying on DNS #1979841

* Tue Jun 22 2021 Mohan Boddu <mboddu@redhat.com> - 3.0.4-2
- Rebuilt for RHEL 9 BETA for openssl 3.0
  Related: rhbz#1971065

* Thu Apr  8 2021 Remi Collet <remi@remirepo.net> - 3.0.4-1
- update to 3.0.4

* Thu Mar  4 2021 Remi Collet <remi@remirepo.net> - 3.0.3-2
- rebuild for https://fedoraproject.org/wiki/Changes/php80

* Mon Feb 22 2021 Remi Collet <remi@remirepo.net> - 3.0.3-1
- update to 3.0.3

* Wed Jan 27 2021 Fedora Release Engineering <releng@fedoraproject.org> - 3.0.2-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_34_Mass_Rebuild

* Tue Jan  5 2021 Remi Collet <remi@remirepo.net> - 3.0.2-1
- update to 3.0.2

* Mon Dec  7 2020 Remi Collet <remi@remirepo.net> - 3.0.1-1
- update to 3.0.1

* Wed Nov 25 2020 Remi Collet <remi@remirepo.net> - 3.0.0-1
- update to 3.0.0 (stable)

* Sun Nov 15 2020 Remi Collet <remi@remirepo.net> - 3.0.0~rc1-1
- update to 3.0.0RC1

* Thu Oct 15 2020 Remi Collet <remi@remirepo.net> - 3.0.0~beta1-1
- update to 3.0.0beta1
- rename to php-pecl-xdebug3 for new API
- debugclient dropped upstream
- raise dependency on PHP 7.2

* Mon Sep 28 2020 Remi Collet <remi@remirepo.net> - 2.9.8-1
- update to 2.9.8

* Wed Sep 16 2020 Remi Collet <remi@remirepo.net> - 2.9.7-1
- update to 2.9.7

* Sat May 30 2020 Remi Collet <remi@remirepo.net> - 2.9.6-1
- update to 2.9.6

* Tue May  5 2020 Remi Collet <remi@remirepo.net> - 2.9.5-2
- rebuild for https://github.com/remicollet/remirepo/issues/146

* Sun Apr 26 2020 Remi Collet <remi@remirepo.net> - 2.9.5-1
- update to 2.9.5

* Mon Mar 23 2020 Remi Collet <remi@remirepo.net> - 2.9.4-1
- update to 2.9.4

* Sat Mar 14 2020 Remi Collet <remi@remirepo.net> - 2.9.3-1
- update to 2.9.3

* Fri Jan 31 2020 Remi Collet <remi@remirepo.net> - 2.9.2-1
- update to 2.9.2

* Thu Jan 16 2020 Remi Collet <remi@remirepo.net> - 2.9.1-1
- update to 2.9.1
- raise dependency on PHP 7.1

* Mon Dec  9 2019 Remi Collet <remi@remirepo.net> - 2.9.0-1
- update to 2.9.0

* Mon Dec  2 2019 Remi Collet <remi@remirepo.net> - 2.8.1-1
- update to 2.8.1

* Thu Oct 31 2019 Remi Collet <remi@remirepo.net> - 2.8.0-1
- update to 2.8.0

* Tue Sep 03 2019 Remi Collet <remi@remirepo.net> - 2.8.0~beta2-2
- rebuild for 7.4.0RC1

* Tue Aug 27 2019 Remi Collet <remi@remirepo.net> - 2.8.0~beta2-1
- update to 2.8.0beta2

* Fri Jul 26 2019 Remi Collet <remi@remirepo.net> - 2.8.0~beta1-1
- update to 2.8.0beta1

* Sat Jun 29 2019 Remi Collet <remi@remirepo.net> - 2.8.0~alpha1-1
- update to 2.8.0alpha1

* Fri Jun 14 2019 Remi Collet <remi@remirepo.net> - 2.8.0~DEV-1.20190614.01167bd
- refresh with PR merged

* Thu Jun 13 2019 Remi Collet <remi@remirepo.net> - 2.8.0~DEV-1.20190613.4ae1efe
- update to 2.8.0-dev for PHP 7.4

* Wed May 29 2019 Remi Collet <remi@remirepo.net> - 2.7.2-2
- rebuild

* Tue May  7 2019 Remi Collet <remi@remirepo.net> - 2.7.2-1
- update to 2.7.2

* Fri Apr  5 2019 Remi Collet <remi@remirepo.net> - 2.7.1-1
- update to 2.7.1

* Thu Mar  7 2019 Remi Collet <remi@remirepo.net> - 2.7.0-1
- update to 2.7.0 (stable)

* Sat Feb 16 2019 Remi Collet <remi@remirepo.net> - 2.7.0~rc2-1
- update to 2.7.0RC2

* Sat Feb  2 2019 Remi Collet <remi@remirepo.net> - 2.7.0~rc1-1
- update to 2.7.0RC1

* Thu Jan 17 2019 Remi Collet <remi@remirepo.net> - 2.7.0~beta1-2
- fix SCL dependency

* Fri Sep 21 2018 Remi Collet <remi@remirepo.net> - 2.7.0~beta1-1
- update to 2.7.0beta1
- add link to documentation in description and configuration file
- open https://github.com/xdebug/xdebug/pull/431 zif_handler in 7.2

* Tue Apr  3 2018 Remi Collet <remi@remirepo.net> - 2.7.0~alpha1-2
- test build for https://github.com/xdebug/xdebug/pull/419

* Mon Apr  2 2018 Remi Collet <remi@remirepo.net> - 2.7.0~alpha1-1
- update to 2.7.0alpha1

* Tue Jan 30 2018 Remi Collet <remi@remirepo.net> - 2.6.0-1
- update to 2.6.0 (stable)

* Mon Jan 29 2018 Remi Collet <remi@remirepo.net> - 2.6.0-0.12.RC2
- Add upstream patch for bigendian

* Tue Jan 23 2018 Remi Collet <remi@remirepo.net> - 2.6.0-0.11.RC2
- update to 2.6.0RC2

* Fri Dec 29 2017 Remi Collet <remi@remirepo.net> - 2.6.0-0.10.beta1
- update to 2.6.0beta1

* Sun Dec  3 2017 Remi Collet <remi@remirepo.net> - 2.6.0-0.9.alpha1
- update to 2.6.0alpha1

* Mon Nov 13 2017 Remi Collet <remi@remirepo.net> - 2.6.0-0.8.20171112.f7a08bc
- refresh

* Wed Oct 18 2017 Remi Collet <remi@remirepo.net> - 2.6.0-0.7.20171018.33ed33d
- refresh with upstream fix for big endian

* Wed Oct 18 2017 Remi Collet <remi@remirepo.net> - 2.6.0-0.6.20171017.89ea903
- refresh and fix test suite
- enable test suite

* Mon Oct  2 2017 Remi Collet <remi@remirepo.net> - 2.6.0-0.5.20170925.9da805c
- rebuild

* Tue Jul 18 2017 Remi Collet <remi@remirepo.net> - 2.6.0-0.4.20170601.d82879d
- rebuild for PHP 7.2.0beta1 new API

* Wed Jun 21 2017 Remi Collet <remi@remirepo.net> - 2.6.0-0.3.20170601.d82879d
- add patch for 7.2.0alpha3 from
  https://github.com/xdebug/xdebug/pull/359

* Wed Jun 21 2017 Remi Collet <remi@remirepo.net> - 2.6.0-0.2.20170601.d82879d
- rebuild for 7.2.0alpha2

* Thu Jun 15 2017 Remi Collet <remi@remirepo.net> - 2.6.0-0.1.20170601.d82879d
- update to 2.6.0-dev for PHP 7.2
- raise dependency on PHP 7

* Mon May 15 2017 Remi Collet <remi@remirepo.net> - 2.5.4-1
- update to 2.5.4

* Mon May  1 2017 Remi Collet <remi@remirepo.net> - 2.5.3-2
- add upstream patch for https://bugs.xdebug.org/view.php?id=1424

* Fri Apr 21 2017 Remi Collet <remi@remirepo.net> - 2.5.3-1
- update to 2.5.3

* Mon Feb 27 2017 Remi Collet <remi@fedoraproject.org> - 2.5.1-2
- use uptream provided configuration with all settings

* Sun Feb 26 2017 Remi Collet <remi@fedoraproject.org> - 2.5.1-1
- Update to 2.5.1

* Mon Dec  5 2016 Remi Collet <remi@fedoraproject.org> - 2.5.0-1
- update to 2.5.0

* Thu Dec  1 2016 Remi Collet <remi@fedoraproject.org> - 2.5.0-0.7.rc1
- rebuild with PHP 7.1.0 GA

* Sat Nov 12 2016 Remi Collet <remi@fedoraproject.org> - 2.5.0-0.6.rc1
- update to 2.5.0RC1

* Wed Oct 12 2016 Remi Collet <remi@fedoraproject.org> - 2.5.0-0.5.20161004git81181b4
- new snapshot of 2.5.0-dev

* Wed Sep 14 2016 Remi Collet <remi@fedoraproject.org> - 2.5.0-0.4.20160731git9fe2994
- rebuild for PHP 7.1 new API version

* Tue Aug  2 2016 Remi Collet <remi@fedoraproject.org> - 2.5.0-0.3.20160731git9fe2994
- new snapshot of 2.5.0-dev

* Fri Jul 29 2016 Remi Collet <remi@fedoraproject.org> - 2.5.0-0.2.20160705git62b3733
- new snapshot of 2.5.0-dev

* Fri Jun 10 2016 Remi Collet <remi@fedoraproject.org> - 2.5.0-0.1.20160529git78fa98b
- update to 2.5.0-dev for PHP 7.1

* Fri Mar  4 2016 Remi Collet <remi@fedoraproject.org> - 2.4.0-1
- update to 2.4.0

* Wed Jan 27 2016 Remi Collet <remi@fedoraproject.org> - 2.4.0-0.8.RC4
- update to 2.4.0RC4

* Sun Dec 13 2015 Remi Collet <remi@fedoraproject.org> - 2.4.0-0.7.RC3
- update to 2.4.0RC3

* Thu Dec  3 2015 Remi Collet <remi@fedoraproject.org> - 2.4.0-0.6.RC2
- update to 2.4.0RC2

* Wed Nov 25 2015 Remi Collet <remi@fedoraproject.org> - 2.4.0-0.5.RC1
- update to 2.4.0RC1

* Thu Nov 19 2015 Remi Collet <remi@fedoraproject.org> - 2.4.0-0.4.20151118git7e4523e
- git snapshot, fix segfault with create_function

* Mon Nov  9 2015 Remi Collet <remi@fedoraproject.org> - 2.4.0-0.2.beta1
- add 1 upstream patch (segfault in code coverage)
  http://bugs.xdebug.org/view.php?id=1195

* Thu Nov  5 2015 Remi Collet <remi@fedoraproject.org> - 2.4.0-0.1.beta1
- update to 2.4.0beta1

* Fri Jun 19 2015 Remi Collet <remi@fedoraproject.org> - 2.3.3-1
- update to 2.3.3
- drop all patches, merged upstream

* Fri May 29 2015 Remi Collet <remi@fedoraproject.org> - 2.3.2-5
- sources from github, with test suite
- run test suite when build using "--with tests" option
- add upstream patch to fix crash when another extension calls
  call_user_function() during RINIT (e.g. phk)

* Fri May 29 2015 Remi Collet <remi@fedoraproject.org> - 2.3.2-4
- add patch for exception code change (for phpunit)

* Wed May 27 2015 Remi Collet <remi@fedoraproject.org> - 2.3.2-3
- add patch for efree/str_efree in php 5.6

* Wed Apr 22 2015 Remi Collet <remi@fedoraproject.org> - 2.3.2-2
- add patch for virtual_file_ex in 5.6 #1214111

* Sun Mar 22 2015 Remi Collet <remi@fedoraproject.org> - 2.3.2-1
- Update to 2.3.2

* Wed Feb 25 2015 Remi Collet <remi@fedoraproject.org> - 2.3.1-1
- Update to 2.3.1

* Mon Feb 23 2015 Remi Collet <remi@fedoraproject.org> - 2.3.0-1
- Update to 2.3.0
- raise minimum php version to 5.4

* Fri Jan 23 2015 Remi Collet <remi@fedoraproject.org> - 2.2.7-2
- fix %%postun scriplet

* Thu Jan 22 2015 Remi Collet <remi@fedoraproject.org> - 2.2.7-1
- Update to 2.2.7
- drop runtime dependency on pear, new scriptlets

* Wed Dec 24 2014 Remi Collet <remi@fedoraproject.org> - 2.2.6-3.1
- Fedora 21 SCL mass rebuild

* Wed Dec  3 2014 Remi Collet <remi@fedoraproject.org> - 2.2.6-3
- more upstream patch

* Wed Dec  3 2014 Remi Collet <remi@fedoraproject.org> - 2.2.6-2
- add upstream patch for couchbase compatibility
  see http://bugs.xdebug.org/view.php?id=1087

* Sun Nov 16 2014 Remi Collet <remi@fedoraproject.org> - 2.2.6-1
- Update to 2.2.6 (stable)

* Mon Aug 25 2014 Remi Collet <rcollet@redhat.com> - 2.2.5-2
- improve SCL build

* Wed Apr 30 2014 Remi Collet <remi@fedoraproject.org> - 2.2.5-1
- Update to 2.2.5 (stable)

* Wed Apr  9 2014 Remi Collet <remi@fedoraproject.org> - 2.2.4-3
- add numerical prefix to extension configuration file
- drop uneeded full extension path

* Wed Mar 19 2014 Remi Collet <rcollet@redhat.com> - 2.2.4-2
- allow SCL build

* Sun Mar 02 2014 Remi Collet <remi@fedoraproject.org> - 2.2.4-1
- Update to 2.2.4 (stable)
- move documentation in pecl_docdir

* Wed May 22 2013 Remi Collet <remi@fedoraproject.org> - 2.2.3-1
- Update to 2.2.3

* Sun Mar 24 2013 Remi Collet <remi@fedoraproject.org> - 2.2.2-1
- update to 2.2.2 (stable)

* Mon Mar 18 2013 Remi Collet <remi@fedoraproject.org> - 2.2.2-0.5.gitb1ce1e3
- new snapshot

* Fri Jan 18 2013 Remi Collet <remi@fedoraproject.org> - 2.2.2-0.4.gitb44a72a
- new snapshot
- drop our patch, merged upstream

* Thu Jan  3 2013 Remi Collet <remi@fedoraproject.org> - 2.2.2-0.3.gite1b9127
- new snapshot
- add patch, see https://github.com/xdebug/xdebug/pull/51

* Fri Nov 30 2012 Remi Collet <remi@fedoraproject.org> - 2.2.2-0.2.gite773b090fc
- rebuild with new php 5.5 snaphost with zend_execute_ex

* Fri Nov 30 2012 Remi Collet <remi@fedoraproject.org> - 2.2.2-0.1.gite773b090fc
- update to git snapshot for php 5.5
- also provides php-xdebug

* Sun Sep  9 2012 Remi Collet <remi@fedoraproject.org> - 2.2.1-2
- sync with rawhide, cleanups
- obsoletes php53*, php54*

* Tue Jul 17 2012 Remi Collet <remi@fedoraproject.org> - 2.2.1-1
- Update to 2.2.1

* Fri Jun 22 2012 Remi Collet <remi@fedoraproject.org> - 2.2.0-2
- upstream patch for upstream bug #838/#839/#840

* Wed May 09 2012 Remi Collet <remi@fedoraproject.org> - 2.2.0-1
- Update to 2.2.0

* Sat Apr 28 2012 Remi Collet <remi@fedoraproject.org> - 2.2.0-0.7.RC2
- Update to 2.2.0RC2

* Wed Mar 14 2012 Remi Collet <remi@fedoraproject.org> - 2.2.0-0.6.RC1
- Update to 2.2.0RC1

* Sun Mar 11 2012 Remi Collet <remi@fedoraproject.org> - 2.2.0-0.5.git8d9993b
- new git snapshot

* Sat Jan 28 2012 Remi Collet <remi@fedoraproject.org> - 2.2.0-0.4.git7e971c4
- new git snapshot
- fix version reported by pecl list

* Fri Jan 20 2012 Remi Collet <remi@fedoraproject.org> - 2.2.0-0.3.git758d962
- new git snapshot

* Sun Dec 11 2011 Remi Collet <remi@fedoraproject.org> - 2.2.0-0.2.gitd076740
- new git snapshot

* Sun Nov 13 2011 Remi Collet <remi@fedoraproject.org> - 2.2.0-0.1.git535df90
- update to 2.2.0-dev, build against php 5.4

* Tue Oct 04 2011 Remi Collet <Fedora@FamilleCollet.com> - 2.1.2-2
- ZTS extension
- spec cleanups

* Thu Jul 28 2011 Remi Collet <Fedora@FamilleCollet.com> - 2.1.2-1
- update to 2.1.2
- fix provides filter for rpm 4.9
- improved description

* Wed Mar 30 2011 Remi Collet <RPMS@FamilleCollet.com> - 2.1.1-1
- allow relocation

* Wed Mar 30 2011 Remi Collet <Fedora@FamilleCollet.com> - 2.1.1-1
- update to 2.1.1
- patch reported version

* Wed Feb 09 2011 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.1.0-3
- Rebuilt for https://fedoraproject.org/wiki/Fedora_15_Mass_Rebuild

* Sat Oct 23 2010 Remi Collet <Fedora@FamilleCollet.com> - 2.1.0-2
- add filter_provides to avoid private-shared-object-provides xdebug.so
- add %%check section (minimal load test)
- always use libedit

* Tue Jun 29 2010 Remi Collet <Fedora@FamilleCollet.com> - 2.1.0-1
- update to 2.1.0

* Mon Sep 14 2009 Christopher Stone <chris.stone@gmail.com> 2.0.5-1
- Upstream sync

* Sun Jul 26 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.0.4-2
- Rebuilt for https://fedoraproject.org/wiki/Fedora_12_Mass_Rebuild

* Sun Jul 12 2009 Remi Collet <Fedora@FamilleCollet.com> - 2.0.4-1
- update to 2.0.4 (bugfix + Basic PHP 5.3 support)

* Thu Feb 26 2009 Fedora Release Engineering <rel-eng@lists.fedoraproject.org> - 2.0.3-5
- Rebuilt for https://fedoraproject.org/wiki/Fedora_11_Mass_Rebuild

* Thu Oct 09 2008 Christopher Stone <chris.stone@gmail.com> 2.0.3-4
- Add code coverage patch (bz #460348)
- http://bugs.xdebug.org/bug_view_page.php?bug_id=0000344

* Thu Oct 09 2008 Christopher Stone <chris.stone@gmail.com> 2.0.3-3
- Revert last change

* Thu Oct 09 2008 Christopher Stone <chris.stone@gmail.com> 2.0.3-2
- Add php-xml to Requires (bz #464758)

* Thu May 22 2008 Christopher Stone <chris.stone@gmail.com> 2.0.3-1
- Upstream sync
- Clean up libedit usage
- Minor rpmlint fix

* Sun Mar 02 2008 Christopher Stone <chris.stone@gmail.com> 2.0.2-4
- Add %%{__pecl} to post/postun Requires

* Fri Feb 22 2008 Christopher Stone <chris.stone@gmail.com> 2.0.2-3
- %%define %%pecl_name to properly register package
- Install xml package description
- Add debugclient
- Many thanks to Edward Rudd (eddie@omegaware.com) (bz #432681)

* Wed Feb 20 2008 Fedora Release Engineering <rel-eng@fedoraproject.org> - 2.0.2-2
- Autorebuild for GCC 4.3

* Sun Nov 25 2007 Christopher Stone <chris.stone@gmail.com> 2.0.2-1
- Upstream sync

* Sun Sep 30 2007 Christopher Stone <chris.stone@gmail.com> 2.0.0-2
- Update to latest standards
- Fix encoding on Changelog

* Sat Sep 08 2007 Christopher Stone <chris.stone@gmail.com> 2.0.0-1
- Upstream sync
- Remove %%{?beta} tags

* Sun Mar 11 2007 Christopher Stone <chris.stone@gmail.com> 2.0.0-0.5.RC2
- Create directory to untar sources
- Use new ABI check for FC6
- Remove %%{release} from Provides

* Mon Jan 29 2007 Christopher Stone <chris.stone@gmail.com> 2.0.0-0.4.RC2
- Compile with $RPM_OPT_FLAGS
- Use %{buildroot} instead of %%{buildroot}
- Fix license tag

* Mon Jan 15 2007 Christopher Stone <chris.stone@gmail.com> 2.0.0-0.3.RC2
- Upstream sync

* Sun Oct 29 2006 Christopher Stone <chris.stone@gmail.com> 2.0.0-0.2.RC1
- Upstream sync

* Wed Sep 06 2006 Christopher Stone <chris.stone@gmail.com> 2.0.0-0.1.beta6
- Remove Provides php-xdebug
- Fix Release
- Remove prior changelog due to Release number change
