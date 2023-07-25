#!/bin/bash

get_netns() {
  ns=$(ip netns identify $$)
  if [ "${ns}" == "" ]; then
    return
  fi
  echo "(${ns}) "
}

export PS1="$( get_netns )$PS1"
