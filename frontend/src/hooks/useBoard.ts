'use client';
import { useQuery, useMutation, useQueryClient } from '@tanstack/react-query';
import {
  fetchTickets,
  createTicket,
  updateTicketStatus,
  type Ticket,
  type TicketStatus,
} from '@/lib/boardSupabase';

export const BOARD_QUERY_KEY = ['board', 'tickets'] as const;

export function useTickets() {
  return useQuery({
    queryKey: BOARD_QUERY_KEY,
    queryFn: fetchTickets,
    staleTime: 30_000,
    refetchInterval: 60_000,
  });
}

export function useCreateTicket() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: createTicket,
    onSuccess: () => qc.invalidateQueries({ queryKey: BOARD_QUERY_KEY }),
  });
}

export function useMoveTicket() {
  const qc = useQueryClient();
  return useMutation({
    mutationFn: ({ id, status }: { id: string; status: TicketStatus }) =>
      updateTicketStatus(id, status),
    onMutate: async ({ id, status }) => {
      await qc.cancelQueries({ queryKey: BOARD_QUERY_KEY });
      const prev = qc.getQueryData<Ticket[]>(BOARD_QUERY_KEY);
      qc.setQueryData<Ticket[]>(BOARD_QUERY_KEY, (old) =>
        old?.map((t) => (t.id === id ? { ...t, status } : t)) ?? []
      );
      return { prev };
    },
    onError: (_err, _vars, ctx) => {
      if (ctx?.prev) qc.setQueryData(BOARD_QUERY_KEY, ctx.prev);
    },
    onSettled: () => qc.invalidateQueries({ queryKey: BOARD_QUERY_KEY }),
  });
}
