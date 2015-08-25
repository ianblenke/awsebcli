VERSIONS:=3.0.1 3.0.2 3.0.3 3.0.4 3.0.5 3.0.6 3.0.7 3.0.8 3.0.9 3.0.10 3.0.11 3.1 3.1.1 3.1.2 3.1.3 3.1.4 3.2 3.2.1 3.2.2 3.3 3.3.1 3.3.2 3.4 3.4.2 3.4.3 3.4.4 3.4.5 3.4.6 3.4.7 3.5

all:
	mkdir -p awsebcli
	cd awsebcli ; git init .
	for version in $(VERSIONS) ; do \
		make awsebcli-$${version}.tar.gz_extracted ; \
	done

%.tar.gz_extracted: %.tar.gz
	tar xvf $(shell echo $@ | cut -d_ -f1) -C $@ --strip-components=1
	rsync -SHPaxv $@/ ./
	git add . ; git commit -a -m $(shell echo $@ | cut -d_ -f1 | sed -e 's/.tar.gz//')

%.tar.gz:
	wget https://pypi.python.org/packages/source/a/awsebcli/$@

clean:
	rm -fr awsebcli *extracted
