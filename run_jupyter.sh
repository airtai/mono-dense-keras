#!/bin/bash

AIRT_DOCKER=ghcr.io/airtai/nbdev-mkdocs:latest
docker pull $AIRT_DOCKER

if test -z "$AIRT_JUPYTER_PORT"
then
      echo 'AIRT_JUPYTER_PORT variable not set, setting to 8888'
      export AIRT_JUPYTER_PORT=8888
else
    echo AIRT_JUPYTER_PORT variable set to $AIRT_JUPYTER_PORT
fi

if test -z "$AIRT_TB_PORT"
then
      echo 'AIRT_TB_PORT variable not set, setting to 6006'
      export AIRT_TB_PORT=6006
else
    echo AIRT_TB_PORT variable set to $AIRT_TB_PORT
fi

if test -z "$AIRT_DASK_PORT"
then
      echo 'AIRT_DASK_PORT variable not set, setting to 8787'
      export AIRT_DASK_PORT=8787
else
    echo AIRT_DASK_PORT variable set to $AIRT_DASK_PORT
fi

if test -z "$AIRT_DOCS_PORT"
then
      echo 'AIRT_DOCS_PORT variable not set, setting to 4000'
      export AIRT_DOCS_PORT=4000
else
    echo AIRT_DOCS_PORT variable set to $AIRT_DOCS_PORT
fi

if test -z "$AIRT_PROJECT"
then
      echo 'AIRT_PROJECT variable not set, setting to current directory'
      export AIRT_PROJECT=`pwd`
fi
echo AIRT_PROJECT variable set to $AIRT_PROJECT

if test -z "$AIRT_GPU_PARAMS"
then
      echo 'AIRT_GPU_PARAMS variable not set, setting to all GPU-s'
      export AIRT_GPU_PARAMS="--gpus all"
fi
echo AIRT_GPU_PARAMS variable set to $AIRT_GPU_PARAMS


echo Using $AIRT_DOCKER
docker image ls $AIRT_DOCKER

if `which nvidia-smi`
then
	echo INFO: Running docker image with: $AIRT_GPU_PARAMS
	nvidia-smi -L
	export GPU_PARAMS=$AIRT_GPU_PARAMS
else
	echo INFO: Running docker image without GPU-s
	export GPU_PARAMS=""
fi

docker run --rm $GPU_PARAMS \
    -e JUPYTER_CONFIG_DIR=/root/.jupyter \
    -p $AIRT_JUPYTER_PORT:8888 -p $AIRT_TB_PORT:6006 -p $AIRT_DASK_PORT:8787 -p $AIRT_DOCS_PORT:4000 \
    -v $AIRT_PROJECT:/work/mono_dense_keras/ \
    -v $HOME/.ssh:$HOME/.ssh -v $HOME/.gitconfig:/root/.gitconfig  \
    -e USER=$USER -e USERNAME=$USERNAME \
    -e GITHUB_TOKEN=$GITHUB_TOKEN \
    $AIRT_DOCKER

#    -v /etc/passwd:/etc/passwd -v /etc/group:/etc/group -v /etc/shadow:/etc/shadow \
