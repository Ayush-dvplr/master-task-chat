# Tape Volume Layout

This note sets how kept replicas are written to tape volumes. It replaces the layout pages of
the 2021 operations handbook.

## 1. Cartridges and capacity

1. Each vault writes to one cartridge type, named by `cartridge` in its section of
   `vault_profiles.ini`.
2. The capacity of a cartridge type is its `native_capacity_bytes` in
   `media_catalogue.json`. Compressed capacity is never used; masters are already
   compressed.
3. Every volume keeps a reserve at the end of tape. The reserve of a cartridge type is the
   value kept in force by charter section 10.
4. Usable capacity of a volume is native capacity minus reserve.

## 2. Footprint of one replica

A replica is written as one tape object: a header of 16384 bytes followed by the file's bytes
padded up to a whole number of blocks. The block size of a vault is `block_size` in
`vault_profiles.ini`.

    footprint = 16384 + ceil(size_bytes / block_size) * block_size

Example with made up numbers: a block size of 131072 and a file of 300000 bytes gives
16384 + 3 * 131072 bytes.

## 3. Packing order

Packing is done per scenario and per vault, over the kept replicas of that vault.

1. Sort the replicas by footprint, largest first. Break ties by digest (lower case hex,
   ascending) and then by `object_path` (plain byte order, ascending).
2. Take the replicas in that order. Put each one on the first open volume, in the order the
   volumes were opened, whose used bytes plus this footprint do not exceed its usable
   capacity. When no open volume has room, open a new volume and put the replica there.
3. A volume's members are listed in the order they were placed.

## 4. Labels and fill

1. Volumes of a vault are numbered 1, 2, 3 and so on in the order they are opened, and
   labelled with the label format kept in force by charter section 10.
2. `used_bytes` of a volume is the sum of the footprints of its members.
3. `fill_bps` is `used_bytes * 10000 / usable_bytes` rounded to the nearest whole number,
   with an exact half rounded to the even neighbour.

## 5. Re-planning against an earlier plan

When the planner is given the output folder of an earlier run as its prior plan:

1. For each scenario name and each vault, read the volumes of that vault from the prior
   scenario file with the same name. A missing prior file means there is no prior plan for
   that scenario.
2. A prior volume is carried over unchanged when every one of its member paths is a kept
   replica of the same vault in the new plan. A carried volume keeps its label and its
   member order; its used bytes and fill are worked out again from the new footprints.
3. A prior volume that loses any member is dissolved. Its remaining members go back into the
   pool.
4. Every kept replica that is not on a carried volume is packed by section 3 into new
   volumes only. New volumes are numbered on from the largest sequence number among all
   prior volumes of that vault in that scenario, carried or dissolved.
5. Carried volumes are listed first, in their prior order, followed by the new volumes.
