cd "/Users/mac/Desktop/Terminal Bench/_runs/20261031/flood-repair-portfolio/fixgate-20261031T121057-69b5/jobs"
for n in 1 2 3; do perl -e 'alarm 2400; exec @ARGV' harbor run --path "/Users/mac/Desktop/Terminal Bench/_runs/20261031/flood-repair-portfolio/fixgate-20261031T121057-69b5/copies/plain" --agent oracle --env docker --job-name oracle-$n --jobs-dir "/Users/mac/Desktop/Terminal Bench/_runs/20261031/flood-repair-portfolio/fixgate-20261031T121057-69b5/jobs" -y; echo "oracle-$n rc $?"; done
echo LANE_DONE
